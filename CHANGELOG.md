# Changelog

## v1.36

- Breaking: Rename `[webtwitchapi]` to `[twitchapi]` and delete the old
  `[twitchapi]` config file entry. See
  [the example config](https://github.com/pajbot/pajbot/blob/677651d416fa60c80ef939df8666bf554237ae0d/install-docs/debian9/kkonatestbroadcaster.ini#L62)
  for example values.
- Breaking: If you want to continue fetching subscribers, you will need to have
  the streamer log in once with `/streamer_login`. Then the bot will
  automatically start fetching a list of subscribers regularly.
- Major: To be able to use game and title updates with `!settitle` and
  `!setgame`, re-authenticate the bot with `/bot_login`. Then ask the streamer
  to add the bot as a channel editor.
- Major: Dependency on `twitch-api-v3-proxy` has been removed. You can uninstall
  that service if you were running it. (The bot now uses the new Twitch v5 and
  Helix APIs)
- Feature: Dubtrack module can now show requester
- Feature: Dubtrack module can automatically post a message when a new song
  starts playing
- Bugfix: Fix a recurring error that could appear when fetching the stream
  live/offline status.
- Bugfix: Make subscriber fetch routine more accurate (will now fetch the
  correct/accurate number of subscribers)
- Bugfix: `!settitle` and `!setgame` are now packaged as a module, you no longer
  need to add these commands as `funccommand`s.
- Bugfix: Updated link checker module to use the latest version of the safe
  browsing API.

## Older versions

Changelogs were not maintained for older pajbot versions.