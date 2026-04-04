# Claude Relay — Project Notes

## What this repo is
A GitHub-based message relay system. Claude instances read and write to this repo using git over HTTPS to pass messages between users. No central server, no app, just git.

## How it works
- Each user has a folder: `messages/[username]/`
- To send: clone repo, write `messages/[recipient]/from_[sender]_[timestamp].txt`, push
- To receive: clone/pull repo, read files in `messages/[username]/`, report to user

## Credentials
- Repo: https://github.com/JohnCheathem/Claude-Relay
- Token: stored separately — ask JohnCheathem
- Anyone using this shares JohnCheathem's GitHub token

## Prompt for new users
Paste this into a fresh Claude conversation, fill in your username:

```
You are a message relay assistant.

CREDENTIALS:
- Repo: https://github.com/JohnCheathem/Claude-Relay.git
- Token: [ASK JOHNCHHEATHEM]
- My username: [YOUR USERNAME HERE]

HOW TO SEND A MESSAGE:
1. git clone https://JohnCheathem:[TOKEN]@github.com/JohnCheathem/Claude-Relay.git /home/claude/Claude-Relay
2. cd /home/claude/Claude-Relay
3. git config user.email "relay@claude.ai" && git config user.name "Claude Relay"
4. mkdir -p messages/[RECIPIENT]
5. echo "[MESSAGE]" > messages/[RECIPIENT]/from_[MY_USERNAME]_$(date +%s).txt
6. git add . && git commit -m "message" && git push https://JohnCheathem:[TOKEN]@github.com/JohnCheathem/Claude-Relay.git main

HOW TO CHECK MY MESSAGES:
1. Clone/pull the repo
2. Read all .txt files in messages/[MY_USERNAME]/
3. Tell me who each message is from
4. Delete read messages and push so inbox stays clean

When I say "check my messages" — do the above.
When I say "tell [person]: [message]" — send it.
```

## Bigger project notes
This relay is a proof of concept for a larger idea discussed in the original conversation:

### P2P file sharing app (the main goal)
- Private circle of known friends, not a public network
- Invite codes for adding friends (one-time, expires after use)
- UPnP to auto-open ports, falls back to manual IP entry
- Direct P2P transfers — no middleman, full connection speed
- Tested Syncthing as an option: hits ~100 MB/s on direct connection with tuned settings
- Key Syncthing fixes: disable relays, set low priority off, set numConnections to 4, blockPullOrder to standard
- DHT considered for peer discovery but private mesh (friends ping each other directly on connect) is simpler and more secure for a closed group

### Messaging
- Same direct connection used for file transfer handles chat too
- GitHub relay (this repo) is a stopgap until direct P2P is built

### Trust & transparency ideas
- Open source the app
- Plain English onboarding explaining exactly what the app does to the system
- Settings page with "safe / things to know" section
- Full activity log of every connection and transfer

## Folder structure
```
messages/
  JohnCheathem/
  Seb/
  [other users]/
notes.md
README.md
```
