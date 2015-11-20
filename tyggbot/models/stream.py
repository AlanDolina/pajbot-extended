import logging
import datetime
import argparse

from tyggbot.models.db import DBManager, Base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import relationship
from sqlalchemy import inspect

log = logging.getLogger('tyggbot')


def parse_twitch_datetime(datetime_str):
    return datetime.datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M:%SZ')


class Stream(Base):
    __tablename__ = 'tb_stream'

    id = Column(Integer, primary_key=True)
    title = Column(String(256), nullable=False)
    stream_start = Column(DateTime, nullable=False)
    stream_end = Column(DateTime, nullable=True)
    ended = Column(Boolean, nullable=False, default=False)

    stream_chunks = relationship('StreamChunk', backref='stream', lazy='subquery')

    def __init__(self, created_at, **options):
        self.id = None
        self.title = options.get('title', 'NO TITLE')
        self.stream_start = parse_twitch_datetime(created_at)
        self.stream_end = None
        self.ended = False

    def refresh(self, status):
        log.debug('Handle stream chunks here?')

class StreamChunk(Base):
    __tablename__ = 'tb_stream_chunk'

    id = Column(Integer, primary_key=True)
    stream_id = Column(Integer, ForeignKey('tb_stream.id'), nullable=False)
    broadcast_id = Column(BIGINT(unsigned=True), nullable=False, unique=True)
    video_url = Column(String(128), nullable=True)
    chunk_start = Column(DateTime, nullable=False)
    chunk_end = Column(DateTime, nullable=True)

    highlights = relationship('StreamChunkHighlight', backref='stream_chunk', lazy='subquery')

    def __init__(self, stream, broadcast_id, created_at, **options):
        self.id = None
        self.stream_id = stream.id
        self.broadcast_id = broadcast_id
        self.video_url = None
        self.chunk_start = parse_twitch_datetime(created_at)
        self.chunk_end = None

        self.stream = stream

class StreamChunkHighlight(Base):
    __tablename__ = 'tb_stream_chunk_highlight'

    id = Column(Integer, primary_key=True)
    stream_chunk_id = Column(Integer, ForeignKey('tb_stream_chunk.id'), nullable=False)
    created_at = Column(DateTime, nullable=False)
    highlight_offset = Column(Integer, nullable=False)
    description = Column(String(128), nullable=True)

    DEFAULT_OFFSET = 0

    def __init__(self, stream_chunk, **options):
        self.stream_chunk_id = stream_chunk.id
        self.created_at = datetime.datetime.now()
        self.highlight_offset = options.get('offset', self.DEFAULT_OFFSET)
        self.description = options.get('description', None)

        self.stream_chunk = stream_chunk

        stream_chunk.highlights.append(self)

class StreamManager:
    NUM_OFFLINES_REQUIRED = 10
    STATUS_CHECK_INTERVAL = 20  # in seconds

    def __init__(self, bot):
        self.bot = bot

        self.current_stream_chunk = None  # should this even exist?

        self.num_offlines = 0
        self.first_offline = None

        self.bot.execute_every(self.STATUS_CHECK_INTERVAL, self.refresh_stream_status)

        """
        This will load the latest stream so we can post an accurate
        "time since last online" figure.
        """
        session = DBManager.create_session()
        self.current_stream = session.query(Stream).filter_by(ended=False).order_by(Stream.stream_start.desc()).first()
        self.last_stream = session.query(Stream).filter_by(ended=True).order_by(Stream.stream_end.desc()).first()
        if self.current_stream and len(self.current_stream.stream_chunks) > 0:
            sorted_chunks = sorted(self.current_stream.stream_chunks, key=lambda x: x.chunk_start, reverse=True)
            self.current_stream_chunk = sorted_chunks[0]
        session.expunge_all()
        session.close()

    @property
    def online(self):
        return self.current_stream is not None

    @property
    def offline(self):
        return self.current_stream is None

    def commit(self):
        log.info('commiting something?')

    def create_stream_chunk(self, status):
        session = DBManager.create_session()
        stream_chunk = session.query(StreamChunk).filter_by(broadcast_id=status['broadcast_id']).one_or_none()
        if stream_chunk is None:
            log.info('Creating stream chunk, from create_stream_chunk')
            stream_chunk = StreamChunk(self.current_stream, status['broadcast_id'], status['created_at'])
            self.current_stream_chunk = stream_chunk
            session.add(stream_chunk)
            session.commit()
        else:
            log.info('We already have a stream chunk!')
            self.current_stream_chunk = stream_chunk
        session.expunge_all()
        session.close()

        self.current_stream.stream_chunks.append(stream_chunk)

    def create_stream(self, status):
        session = DBManager.create_session()

        stream_chunk = session.query(StreamChunk).filter_by(broadcast_id=status['broadcast_id']).one_or_none()

        log.info('Attempting to create a stream!')

        if stream_chunk is not None:
            log.info('we already have a stream chunk OMGScoots')
            log.info(stream_chunk)
            log.info(stream_chunk.stream_id)
            log.info(stream_chunk.stream)
            stream = stream_chunk.stream
        else:
            log.info('checking if there is an active stream already')
            stream = session.query(Stream).filter_by(ended=False).order_by(Stream.stream_start.desc()).first()

            if stream is None:
                log.info('No active stream, create new!')
                stream = Stream(status['created_at'],
                        title=status['title'])
                session.add(stream)
                session.commit()
                stream.expunge()
                log.info('added stream!')
            stream_chunk = StreamChunk(stream, status['broadcast_id'], status['created_at'])
            session.add(stream_chunk)
            session.commit()
            stream_chunk.expunge()
            stream.stream_chunks.append(stream_chunk)
            log.info('Created stream chunk')

        self.current_stream = stream
        self.current_stream_chunk = stream_chunk

        log.info('added shit to current_stream etc')

        session.expunge_all()
        session.close()

    def go_offline(self):
        session = DBManager.create_session()
        session.add(self.current_stream)
        session.add(self.current_stream_chunk)
        session.commit()
        session.expunge_all()
        session.close()

    def refresh_stream_status(self):
        try:
            status = self.bot.twitchapi.get_status(self.bot.streamer)
            if status['error'] is True:
                log.error('An error occured while fetching stream status')
                return

            if status['online']:
                if self.current_stream is None:
                    self.create_stream(status)
                if self.current_stream_chunk is None:
                    self.create_stream_chunk(status)
                    self.current_stream.refresh(status)
                self.num_offlines = 0
                self.first_offline = None
                self.bot.ascii_timeout_duration = 120
                self.bot.msg_length_timeout_duration = 120
            else:
                self.bot.ascii_timeout_duration = 10
                self.bot.msg_length_timeout_duration = 10
                if self.online is True:
                    log.info('Offline. {0}'.format(self.num_offlines))
                    if self.first_offline is None:
                        self.first_offline = datetime.datetime.now()

                    if self.num_offlines >= 10:
                        log.info('Switching to offline state!')
                        self.current_stream.ended = True
                        self.current_stream.stream_end = self.first_offline
                        self.last_stream = self.current_stream
                        self.current_stream_chunk.chunk_end = self.first_offline
                        self.go_offline()
                        self.current_stream = None
                        self.current_stream_chunk = None
                    self.num_offlines += 1
        except:
            log.exception('Uncaught exception while refreshing stream status')

    def create_highlight(self, **options):
        """
        Returns an error message (string) if something went wrong, otherwise returns True
        """
        if self.online is False or self.current_stream_chunk is None:
            return 'The stream is not online'

        try:
            highlight = StreamChunkHighlight(self.current_stream_chunk, **options)

            session = DBManager.create_session(expire_on_commit=False)
            session.add(highlight)
            session.add(self.current_stream_chunk)
            session.commit()
            session.close()

            x = inspect(self.current_stream_chunk)
            log.info('{0.transient} - {0.pending} - {0.persistent} - {0.detached}'.format(x))
            x = inspect(highlight)
            log.info('{0.transient} - {0.pending} - {0.persistent} - {0.detached}'.format(x))
            x = inspect(self.current_stream)
            log.info('{0.transient} - {0.pending} - {0.persistent} - {0.detached}'.format(x))

            log.info(self.current_stream.id)
            log.info(highlight.id)
            log.info(self.current_stream_chunk.id)
        except:
            log.exception('uncaught exception in create_highlight')
            return 'Unknown reason, ask pajlada'

        return True

    def parse_highlight_arguments(self, message):
        parser = argparse.ArgumentParser()
        parser.add_argument('--offset', dest='offset', type=int)

        try:
            args, unknown = parser.parse_known_args(message.split())
        except SystemExit:
            return False, False
        except:
            log.exception('Unhandled exception in add_highlight')
            return False, False

        # Strip options of any values that are set as None
        options = {k: v for k, v in vars(args).items() if v is not None}
        response = ' '.join(unknown)

        return options, response
