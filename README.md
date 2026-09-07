# ODEON Seat Blocker

CLI tool to block up to 9 seats at ODEON cinemas for 12 minutes at a time.

## What it does

Blocks seats to make cinemas appear busy without actually buying tickets. Run repeatedly to keep seats blocked indefinitely.

## How it works

1. Select cinema, film, showtime
2. Choose seats (e.g., `C1-4` for seats C1-C4)
3. Blocks them for 12 minutes
4. Run again to re-block

## Visual Guide

<img src="imgs/1.png" alt="Step 1" width="600">

<img src="imgs/2.png" alt="Step 2" width="600">

<img src="imgs/3.png" alt="Step 3" width="600">

<img src="imgs/4.png" alt="Step 4" width="600">

<img src="imgs/5.png" alt="Step 5" width="600">

<img src="imgs/6.png" alt="Step 6" width="600">

<img src="imgs/7.png" alt="Step 7" width="600">

<img src="imgs/8.png" alt="Step 8" width="600">

<img src="imgs/9.png" alt="Step 9" width="600">

## Install

```bash
pip install requests
```

## Use

```bash
python odeon_reservation.py
```

## Note

- Max 9 seats per run
- Blocks last 12 minutes
- Re-run to maintain block
