# **ODEON Seat Blocker**

CLI tool demonstrating seat-reservation/session-hold behaviour for educational and authorized testing purposes.

## **Disclaimer**

This project is provided **for educational, research, and authorized testing purposes only**.

Do not use it against systems, cinemas, accounts, or services that you do not own or have explicit permission to test. The author does not encourage or authorize misuse of this software and accepts no responsibility for unauthorized, unlawful, abusive, or disruptive use by third parties.

You are solely responsible for ensuring that your use complies with applicable laws, terms of service, and permissions.

## **What it does**

Demonstrates how temporary cinema seat holds can work without completing a ticket purchase.

## **How it works**

1. Select cinema, film, and showtime
2. Choose seats (e.g. `C1-4` for seats C1-C4)
3. Creates a temporary seat hold
4. The hold expires after the applicable reservation period

## **Beta** 

1. Book entire cinema out.
2. Draw patterns in seat layout. - broken
3. Auto-select N contiguous seats

## **Visual Guide**

<img src="imgs/1.png" alt="Step 1" width="600">

<img src="imgs/2.png" alt="Step 2" width="600">

<img src="imgs/3.png" alt="Step 3" width="600">

<img src="imgs/4.png" alt="Step 4" width="600">

<img src="imgs/5.png" alt="Step 5" width="600">

<img src="imgs/6.png" alt="Step 6" width="600">

<img src="imgs/7.png" alt="Step 7" width="600">

<img src="imgs/8.png" alt="Step 8" width="600">

<img src="imgs/9.png" alt="Step 9" width="600">

## **Install**

```bash
pip install requests
```

## **Use**

```bash
python odeon_book_tickets.py
```
```bash
python odeon_book_beta.py
```
## **Note**

* Intended only for systems you own or are explicitly authorized to test
* Temporary holds expire automatically
* Do not use this software to disrupt genuine customers or booking availability
