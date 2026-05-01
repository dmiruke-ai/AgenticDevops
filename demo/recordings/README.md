# Demo Recordings

Terminal recordings using [asciinema](https://asciinema.org/).

## Available Recordings

| Recording | Description | Duration |
|-----------|-------------|----------|
| [demo-quick.cast](demo-quick.cast) | Quick demo (mock mode) | ~90 sec |
| [demo-up.cast](demo-up.cast) | Full stack demo | ~2 min |
| [aws-up.cast](aws-up.cast) | AWS deployment | ~3 min |

## How to View

### Option 1: Web Player (Recommended)
Upload to [asciinema.org](https://asciinema.org/docs/embedding) and embed in README.

### Option 2: Local Playback
```bash
# Install asciinema
pip install asciinema

# Play recording
asciinema play demo/recordings/demo-quick.cast
```

### Option 3: Convert to GIF
```bash
# Install agg (asciinema gif generator)
cargo install --git https://github.com/asciinema/agg

# Convert to GIF
agg demo/recordings/demo-quick.cast demo-quick.gif
```

## Recording New Demos

```bash
# Record demo-quick
make record-demo-quick

# Record demo-up
make record-demo-up

# Record AWS deployment
make record-aws-up
```

## Embedding in README

```markdown
[![asciicast](https://asciinema.org/a/YOUR_ID.svg)](https://asciinema.org/a/YOUR_ID)
```
