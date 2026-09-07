from __future__ import annotations

import difflib
import json
import logging
import os
import re
import shutil
import sys
import time
import traceback
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue

import requests

BOOTSTRAP_URL = "https://www.odeon.co.uk/"
MAX_SEATS = 9
DEFAULT_TIMEOUT = 30
LOG_DIR = Path("logs")
ENV_PATH = Path(__file__).resolve().with_name(".env")
PRIVACY_MODE = True
PRIVATE_CINEMA_NAME = "Your Cinema"
PRIVATE_SITE_ID = "<hidden>"

SITE_ID = ""
SITE_NAME = ""

if os.name == "nt":
    os.system("")

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"
BG_BLUE = "\033[44m"

SECRET_KEYS = {
    "authorization",
    "auth",
    "authtoken",
    "token",
    "access_token",
    "refresh_token",
    "cookie",
    "set-cookie",
    "cf_clearance",
}


def terminal_size() -> tuple[int, int]:
    size = shutil.get_terminal_size((100, 30))
    return size.columns, size.lines


def clear_screen():
    sys.stdout.write("\033[H\033[2J")
    sys.stdout.flush()


def line(char="─", width=None):
    if width is None:
        columns, _ = terminal_size()
        width = max(40, min(columns - 2, 96))
    print(DIM + char * width + RESET)


def title(text: str, subtitle: str | None = None):
    clear_screen()
    print()
    print(BG_BLUE + WHITE + BOLD + "  ODEON RESERVATION  " + RESET)
    print()
    print(BOLD + CYAN + text + RESET)

    if subtitle:
        print(DIM + subtitle + RESET)

    line()


def success(text: str):
    print(GREEN + "✓ " + text + RESET)


def warning(text: str):
    print(YELLOW + "! " + text + RESET)


def error(text: str):
    print(RED + "✗ " + text + RESET)


def info(text: str):
    print(CYAN + "• " + text + RESET)


def prompt(text: str) -> str:
    return input(BOLD + CYAN + "> " + RESET + text).strip()


def wait_for_enter(message="Press Enter to continue..."):
    input(DIM + message + RESET)


def display_cinema_name(name: str | None = None) -> str:
    if PRIVACY_MODE:
        return PRIVATE_CINEMA_NAME

    return name or SITE_NAME or PRIVATE_CINEMA_NAME


def display_site_id(site_id: str | None = None) -> str:
    if PRIVACY_MODE:
        return PRIVATE_SITE_ID

    return site_id or SITE_ID or PRIVATE_SITE_ID


def selected_box(
    film: str | None = None,
    date: str | None = None,
    showtime: str | None = None,
    seats: str | None = None,
    ticket: str | None = None,
):
    values = [
        ("Film", film),
        ("Date", date),
        ("Time", showtime),
        ("Seats", seats),
        ("Ticket", ticket),
    ]

    values = [
        (key, value)
        for key, value in values
        if value
    ]

    if not values:
        return

    print()
    print(DIM + "Current selection" + RESET)

    for label, value in values:
        print(
            f"  {DIM}{label:<7}{RESET} "
            f"{value}"
        )

    print()


def setup_logging() -> tuple[logging.Logger, Path]:
    LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    stamp = datetime.now().strftime(
        "%Y-%m-%d_%H-%M-%S"
    )

    path = (
        LOG_DIR
        / f"odeon_reservation_{stamp}.log"
    )

    logger = logging.getLogger(
        "odeon"
    )

    logger.setLevel(
        logging.DEBUG
    )

    logger.handlers.clear()

    handler = logging.FileHandler(
        path,
        encoding="utf-8",
    )

    handler.setLevel(
        logging.DEBUG
    )

    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    logger.addHandler(
        handler
    )

    return logger, path


LOGGER, LOG_PATH = setup_logging()


def private_string(value: str) -> str:
    result = value

    if SITE_NAME:
        result = re.sub(
            re.escape(SITE_NAME),
            PRIVATE_CINEMA_NAME,
            result,
            flags=re.I,
        )

    if SITE_ID:
        result = re.sub(
            rf"(?<!\d){re.escape(SITE_ID)}(?=(?:[-/]|$))",
            PRIVATE_SITE_ID,
            result,
        )

    return result


def redact(value: Any) -> Any:
    if isinstance(
        value,
        dict,
    ):
        output = {}

        for key, item in value.items():
            lowered = str(
                key
            ).lower()

            if lowered in SECRET_KEYS:
                output[key] = (
                    "<REDACTED>"
                )

            elif (
                PRIVACY_MODE
                and lowered
                in {
                    "siteid",
                    "site_id",
                    "sitename",
                    "site_name",
                    "cinema",
                    "cinemaname",
                }
            ):
                output[key] = (
                    "<PRIVATE>"
                )

            else:
                output[key] = (
                    redact(item)
                )

        return output

    if isinstance(
        value,
        list,
    ):
        return [
            redact(item)
            for item in value
        ]

    if isinstance(
        value,
        str,
    ):
        return private_string(
            value
        )

    return value


def log_json(
    label: str,
    value: Any,
):
    try:
        LOGGER.debug(
            "%s\n%s",
            label,
            json.dumps(
                redact(value),
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
        )

    except Exception:
        LOGGER.debug(
            "%s\n%s",
            label,
            repr(
                redact(value)
            ),
        )


LOGGER.info(
    "Application start"
)

LOGGER.info(
    "Python executable: %s",
    sys.executable,
)

LOGGER.info(
    "Python version: %s",
    sys.version.replace(
        "\n",
        " ",
    ),
)

LOGGER.info(
    "Requests version: %s",
    requests.__version__,
)

LOGGER.info(
    "Script path: %s",
    Path(__file__).resolve(),
)

LOGGER.info(
    "Working directory: %s",
    Path.cwd(),
)

LOGGER.info(
    "Privacy mode: %s",
    PRIVACY_MODE,
)


class ApiError(RuntimeError):
    def __init__(
        self,
        method: str,
        path: str,
        status_code: int,
        payload: Any,
    ):
        self.method = method
        self.path = path
        self.status_code = status_code
        self.payload = payload

        api_title = ""
        detail = ""

        if isinstance(
            payload,
            dict,
        ):
            api_title = str(
                payload.get("title")
                or ""
            )

            detail = str(
                payload.get("detail")
                or ""
            )

        message = (
            f"{method} "
            f"{private_string(path)} "
            f"failed with HTTP "
            f"{status_code}"
        )

        if api_title:
            message += (
                f" | {api_title}"
            )

        if detail:
            message += (
                f" | detail={detail}"
            )

        super().__init__(
            message
        )


def extract_assigned_json(
    text: str,
    marker: str,
) -> dict[str, Any]:
    marker_pos = text.find(
        marker
    )

    if marker_pos < 0:
        raise ValueError(
            f"Could not find {marker}"
        )

    start = text.find(
        "{",
        marker_pos
        + len(marker),
    )

    if start < 0:
        raise ValueError(
            "JSON object not found"
        )

    depth = 0
    in_string = False
    escaped = False

    for pos in range(
        start,
        len(text),
    ):
        char = text[pos]

        if in_string:
            if escaped:
                escaped = False

            elif char == "\\":
                escaped = True

            elif char == '"':
                in_string = False

            continue

        if char == '"':
            in_string = True

        elif char == "{":
            depth += 1

        elif char == "}":
            depth -= 1

            if depth == 0:
                return json.loads(
                    text[
                        start:
                        pos + 1
                    ]
                )

    raise ValueError(
        "Unterminated JSON"
    )


@dataclass
class Bootstrap:
    api_root: str
    token: str
    region: str


def bootstrap(
    session: requests.Session,
    timeout: int,
) -> Bootstrap:
    title(
        "Connecting",
        "ODEON UK",
    )

    info(
        "Loading public API configuration..."
    )

    started = (
        time.perf_counter()
    )

    response = session.get(
        BOOTSTRAP_URL,
        timeout=timeout,
        allow_redirects=True,
        headers={
            "Accept":
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8",

            "Accept-Language":
                "en-GB,en;q=0.9",

            "User-Agent":
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36",
        },
    )

    elapsed = (
        time.perf_counter()
        - started
    )

    LOGGER.info(
        "BOOTSTRAP HTTP %s "
        "%.3fs final_url=%s bytes=%s",
        response.status_code,
        elapsed,
        response.url,
        len(
            response.content
        ),
    )

    response.raise_for_status()

    try:
        data = extract_assigned_json(
            response.text,
            "window.initialData",
        )

    except Exception as exc:
        lower = (
            response.text.lower()
        )

        if (
            "queue-it" in lower
            or "queueit" in lower
        ):
            reason = (
                "Queue-it page returned"
            )

        elif (
            "cloudflare" in lower
            or "cf-chl-" in lower
        ):
            reason = (
                "Cloudflare challenge returned"
            )

        else:
            reason = (
                "window.initialData missing"
            )

        raise RuntimeError(
            f"Bootstrap failed: {reason}"
        ) from exc

    api = (
        data.get("api")
        or {}
    )

    api_url = api.get(
        "apiUrl"
    )

    token = api.get(
        "authToken"
    )

    region = api.get(
        "regionCode"
    )

    if not all(
        isinstance(item, str)
        and item
        for item in (
            api_url,
            token,
            region,
        )
    ):
        raise RuntimeError(
            "Missing API bootstrap values"
        )

    api_root = (
        api_url.rstrip("/")
        + "/ocapi/v1"
    )

    success(
        f"Connected to {region} API "
        f"in {elapsed:.2f}s"
    )

    LOGGER.info(
        "API root: %s",
        api_root,
    )

    LOGGER.info(
        "Region: %s",
        region,
    )

    LOGGER.info(
        "Token acquired automatically"
    )

    time.sleep(
        0.25
    )

    return Bootstrap(
        api_root,
        token,
        region,
    )


class OdeonAPI:
    def __init__(
        self,
        site_id: str = "",
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.site_id = site_id
        self.timeout = timeout

        self.session = (
            requests.Session()
        )

        boot = bootstrap(
            self.session,
            timeout,
        )

        self.api_root = (
            boot.api_root
        )

        self.apply_headers(
            boot
        )

    def apply_headers(
        self,
        boot: Bootstrap,
    ):
        self.session.headers.update(
            {
                "Accept":
                    "application/json",

                "Authorization":
                    f"Bearer {boot.token}",

                "connect-region-code":
                    boot.region,

                "Origin":
                    "https://www.odeon.co.uk",

                "Referer":
                    "https://www.odeon.co.uk/",

                "User-Agent":
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/140.0.0.0 Safari/537.36",
            }
        )

    def request(
        self,
        method: str,
        path: str,
        params: Any = None,
        json_body: Any = None,
        silent: bool = False,
    ) -> dict[str, Any]:
        url = (
            self.api_root.rstrip("/")
            + "/"
            + path.lstrip("/")
        )

        request_id = (
            uuid.uuid4().hex[:8]
        )

        safe_path = (
            private_string(path)
        )

        LOGGER.debug(
            "REQUEST [%s] %s %s "
            "params=%s body=%s",
            request_id,
            method,
            private_string(url),
            redact(params),
            redact(json_body),
        )

        started = (
            time.perf_counter()
        )

        try:
            response = (
                self.session.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    timeout=self.timeout,
                )
            )

        except requests.RequestException as exc:
            elapsed = (
                time.perf_counter()
                - started
            )

            LOGGER.exception(
                "TRANSPORT_ERROR [%s] "
                "%s %s after %.3fs "
                "exception=%s",
                request_id,
                method,
                safe_path,
                elapsed,
                exc.__class__.__name__,
            )

            raise

        elapsed = (
            time.perf_counter()
            - started
        )

        correlation = (
            response.headers.get(
                "correlationid"
            )
            or response.headers.get(
                "x-correlation-id"
            )
            or "-"
        )

        LOGGER.info(
            "RESPONSE [%s] %s %s "
            "HTTP %s %.3fs "
            "correlation=%s bytes=%s",
            request_id,
            method,
            safe_path,
            response.status_code,
            elapsed,
            correlation,
            len(
                response.content
            ),
        )

        if not silent:
            print(
                DIM
                + f"{method} "
                + f"{safe_path} "
                + RESET
                + (
                    GREEN
                    if response.ok
                    else RED
                )
                + f"[{response.status_code}]"
                + RESET
                + DIM
                + f" {elapsed:.2f}s"
                + RESET
            )

        try:
            payload = (
                response.json()
            )

        except ValueError:
            payload = {
                "raw":
                    response.text
            }

        log_json(
            f"RESPONSE "
            f"[{request_id}] "
            f"{method} {safe_path}",
            payload,
        )

        if not response.ok:
            raise ApiError(
                method,
                path,
                response.status_code,
                payload,
            )

        return payload

    def refresh_session(
        self,
    ):
        LOGGER.info(
            "Refreshing API session"
        )

        new_session = (
            requests.Session()
        )

        boot = bootstrap(
            new_session,
            self.timeout,
        )

        self.session = (
            new_session
        )

        self.api_root = (
            boot.api_root
        )

        self.apply_headers(
            boot
        )

        LOGGER.info(
            "API session refreshed"
        )

    def sites(
        self,
    ):
        return self.request(
            "GET",
            "sites",
            silent=True,
        )

    def films_for_site(
        self,
    ):
        return self.request(
            "GET",
            f"sites/{self.site_id}/films",
            silent=True,
        )

    def screening_dates(
        self,
        film_id: str,
    ):
        return self.request(
            "GET",
            "film-screening-dates",
            params=[
                (
                    "filmIds",
                    film_id,
                ),
                (
                    "siteIds",
                    self.site_id,
                ),
            ],
            silent=True,
        )

    def first_showtimes(
        self,
        film_id: str,
    ):
        return self.request(
            "GET",
            "showtimes/by-business-date/first",
            params=[
                (
                    "filmIds",
                    film_id,
                ),
                (
                    "siteIds",
                    self.site_id,
                ),
            ],
            silent=True,
        )

    def showtimes_for_date(
        self,
        film_id: str,
        business_date: str,
    ):
        return self.request(
            "GET",
            f"showtimes/by-business-date/"
            f"{business_date}",
            params=[
                (
                    "filmIds",
                    film_id,
                ),
                (
                    "siteIds",
                    self.site_id,
                ),
            ],
            silent=True,
        )

    def seat_layout(
        self,
        seat_layout_id: str,
    ):
        return self.request(
            "GET",
            f"seat-layouts/"
            f"{seat_layout_id}",
            silent=True,
        )

    def seat_availability(
        self,
        showtime_id: str,
    ):
        return self.request(
            "GET",
            f"showtimes/"
            f"{showtime_id}/"
            f"seat-availability",
            silent=True,
        )

    def seat_availability_with_retry(
        self,
        showtime_id: str,
    ):
        try:
            return (
                self.seat_availability(
                    showtime_id
                )
            )

        except ApiError as exc:
            if (
                exc.status_code
                != 403
            ):
                raise

            LOGGER.warning(
                "Seat availability returned "
                "HTTP 403; refreshing session "
                "and retrying once"
            )

            warning(
                "Seat availability returned HTTP 403."
            )

            info(
                "Refreshing API session "
                "and retrying once..."
            )

            self.refresh_session()

            return (
                self.seat_availability(
                    showtime_id
                )
            )

    def ticket_prices(
        self,
        showtime_id: str,
    ):
        return self.request(
            "GET",
            f"showtimes/"
            f"{showtime_id}/"
            f"ticket-prices",
            silent=True,
        )

    def create_order(
        self,
    ):
        return self.request(
            "POST",
            "orders/standard/booking",
            json_body={
                "siteId":
                    self.site_id,

                "bookingMode":
                    "Paid",
            },
        )

    def set_showtime(
        self,
        order_id: str,
        showtime_id: str,
        seats: list[str],
        tickets: list[dict[str, str]],
    ):
        return self.request(
            "PUT",
            f"orders/"
            f"{order_id}/"
            f"showtimes/"
            f"{showtime_id}",
            json_body={
                "seats":
                    seats,

                "tickets":
                    tickets,
            },
        )


def text_value(
    value: Any,
) -> str:
    if isinstance(
        value,
        str,
    ):
        return value

    if isinstance(
        value,
        dict,
    ):
        return str(
            value.get("text")
            or value.get("name")
            or ""
        )

    return str(
        value
        or ""
    )


def find_list(
    payload: dict[str, Any],
    *keys: str,
) -> list[dict[str, Any]]:
    for key in keys:
        value = payload.get(
            key
        )

        if isinstance(
            value,
            list,
        ):
            return [
                item
                for item in value
                if isinstance(
                    item,
                    dict,
                )
            ]

    related = payload.get(
        "relatedData"
    )

    if isinstance(
        related,
        dict,
    ):
        for key in keys:
            value = related.get(
                key
            )

            if isinstance(
                value,
                list,
            ):
                return [
                    item
                    for item in value
                    if isinstance(
                        item,
                        dict,
                    )
                ]

    return []


def load_env_file() -> dict[str, str]:
    try:
        lines = (
            ENV_PATH.read_text(
                encoding="utf-8"
            ).splitlines()
        )

    except OSError:
        return {}

    values = {}

    for raw in lines:
        line_value = (
            raw.strip()
        )

        if (
            not line_value
            or "=" not in line_value
        ):
            continue

        key, value = (
            line_value.split(
                "=",
                1,
            )
        )

        key = key.strip()
        value = value.strip()

        if (
            len(value) >= 2
            and value[0]
            == value[-1]
            and value[0]
            in {
                "'",
                '"',
            }
        ):
            value = (
                value[1:-1]
            )

        values[key] = value

    return values


def env_quote(
    value: str,
) -> str:
    escaped = (
        value.replace(
            "\\",
            "\\\\",
        ).replace(
            '"',
            '\\"',
        )
    )

    return (
        f'"{escaped}"'
    )


def load_saved_cinema_name() -> str | None:
    data = (
        load_env_file()
    )

    site_name = str(
        data.get(
            "ODEON_SITE_NAME"
        )
        or ""
    ).strip()

    return (
        site_name
        or None
    )


def save_cinema_name(
    site_name: str,
):
    existing = (
        load_env_file()
    )

    existing.pop(
        "ODEON_SITE_ID",
        None,
    )

    existing[
        "ODEON_SITE_NAME"
    ] = site_name

    preferred = [
        "ODEON_SITE_NAME"
    ]

    keys = (
        preferred
        + sorted(
            key
            for key
            in existing
            if key
            not in preferred
        )
    )

    content = (
        "\n".join(
            f"{key}="
            f"{env_quote(existing[key])}"
            for key
            in keys
        )
        + "\n"
    )

    ENV_PATH.write_text(
        content,
        encoding="utf-8",
    )


def parse_sites(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    sites = payload.get(
        "sites"
    )

    if not isinstance(
        sites,
        list,
    ):
        sites = find_list(
            payload,
            "sites",
            "items",
            "value",
        )

    result = []

    for site in sites:
        if not isinstance(
            site,
            dict,
        ):
            continue

        site_id = str(
            site.get("id")
            or site.get("siteId")
            or ""
        ).strip()

        name = text_value(
            site.get("name")
        ).strip()

        if (
            not site_id
            or not name
        ):
            continue

        contact = (
            site.get(
                "contactDetails"
            )
            or {}
        )

        address = (
            contact.get(
                "address"
            )
            or {}
        )

        city = (
            str(
                address.get("city")
                or ""
            ).strip()
            if isinstance(
                address,
                dict,
            )
            else ""
        )

        result.append(
            {
                "id":
                    site_id,

                "name":
                    name,

                "city":
                    city,
            }
        )

    return result


def normalise_name(
    value: str,
) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "",
        value.lower(),
    )


def cinema_score(
    query: str,
    site: dict[str, Any],
) -> float:
    q = normalise_name(
        query
    )

    name = normalise_name(
        site["name"]
    )

    city = normalise_name(
        site.get("city")
        or ""
    )

    if not q:
        return 0.0

    if (
        q == name
        or (
            city
            and q == city
        )
    ):
        return 100.0

    scores = [
        difflib.SequenceMatcher(
            None,
            q,
            name,
        ).ratio()
        * 100
    ]

    if city:
        scores.append(
            difflib.SequenceMatcher(
                None,
                q,
                city,
            ).ratio()
            * 100
        )

    if name.startswith(
        q
    ):
        scores.append(
            min(
                99.0,
                80.0
                + len(q)
                / max(
                    1,
                    len(name),
                )
                * 19.0,
            )
        )

    if (
        city
        and city.startswith(
            q
        )
    ):
        scores.append(
            min(
                99.0,
                80.0
                + len(q)
                / max(
                    1,
                    len(city),
                )
                * 19.0,
            )
        )

    return max(
        scores
    )


def choose_cinema(
    api: OdeonAPI,
) -> tuple[str, str]:
    title(
        "Choose your cinema",
        "Loading live ODEON cinemas",
    )

    sites = parse_sites(
        api.sites()
    )

    if not sites:
        raise RuntimeError(
            "No cinemas were returned "
            "by the sites endpoint"
        )

    saved_name = (
        load_saved_cinema_name()
    )

    if saved_name:
        matches = sorted(
            [
                (
                    cinema_score(
                        saved_name,
                        site,
                    ),
                    site,
                )
                for site
                in sites
            ],
            key=lambda item:
                item[0],
            reverse=True,
        )

        if matches:
            _, best = (
                matches[0]
            )

            title(
                "Your cinema",
                display_cinema_name(
                    best["name"]
                ),
            )

            success(
                f"Using saved cinema: "
                f"{display_cinema_name(best['name'])}"
            )

            print()

            print(
                DIM
                + "Press Enter to continue, "
                + "c to change cinema."
                + RESET
            )

            choice = prompt(
                "Choice: "
            ).lower()

            if choice not in {
                "c",
                "change",
            }:
                return (
                    best["id"],
                    best["name"],
                )

    while True:
        title(
            "Choose your cinema",
            f"{len(sites)} cinemas available",
        )

        print()

        print(
            "Type part of the cinema name."
        )

        print(
            DIM
            + "Example: Lond, Manch"
            + RESET
        )

        print()

        query = prompt(
            "Cinema: "
        )

        if query.lower() in {
            "q",
            "quit",
            "exit",
        }:
            raise KeyboardInterrupt

        if not query:
            continue

        matches = sorted(
            [
                (
                    cinema_score(
                        query,
                        site,
                    ),
                    site,
                )
                for site
                in sites
            ],
            key=lambda item:
                item[0],
            reverse=True,
        )

        if not matches:
            error(
                "No cinema match found."
            )

            time.sleep(
                0.7
            )

            continue

        score, best = (
            matches[0]
        )

        title(
            "Confirm cinema",
            f"{score:.0f}% match",
        )

        print()

        print(
            f"Did you mean "
            f"{BOLD}{CYAN}"
            f"{best['name']}"
            f"{RESET}?"
        )

        if best.get(
            "city"
        ):
            print(
                DIM
                + f"City: {best['city']}"
                + RESET
            )

        print()

        answer = prompt(
            "Use this cinema? [Y/n]: "
        ).lower()

        if answer in {
            "",
            "y",
            "yes",
        }:
            save_cinema_name(
                best["name"]
            )

            success(
                "Cinema saved."
            )

            time.sleep(
                0.4
            )

            return (
                best["id"],
                best["name"],
            )

        alternatives = (
            matches[:5]
        )

        title(
            "Other matches",
            query,
        )

        for index, (
            alt_score,
            site,
        ) in enumerate(
            alternatives,
            1,
        ):
            city = (
                f" · {site['city']}"
                if site.get("city")
                else ""
            )

            print(
                f"{CYAN}"
                f"{index:>2}."
                f"{RESET} "
                f"{BOLD}"
                f"{site['name']}"
                f"{RESET}"
                f"{DIM}"
                f"{city} · "
                f"{alt_score:.0f}%"
                f"{RESET}"
            )

        print()

        raw = prompt(
            "Number or Enter "
            "to search again: "
        )

        if not raw:
            continue

        try:
            index = int(
                raw
            )

        except ValueError:
            continue

        if (
            1
            <= index
            <= len(alternatives)
        ):
            _, chosen = (
                alternatives[
                    index - 1
                ]
            )

            save_cinema_name(
                chosen["name"]
            )

            success(
                "Cinema saved."
            )

            time.sleep(
                0.4
            )

            return (
                chosen["id"],
                chosen["name"],
            )


def parse_films(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    films = find_list(
        payload,
        "films",
        "items",
        "value",
    )

    result = []
    seen = set()

    for film in films:
        film_id = str(
            film.get("id")
            or film.get("ID")
            or film.get("filmId")
            or film.get(
                "ScheduledFilmId"
            )
            or ""
        )

        if (
            not film_id
            or film_id in seen
        ):
            continue

        result.append(
            {
                "id":
                    film_id,

                "title":
                    text_value(
                        film.get("title")
                    )
                    or str(
                        film.get("Title")
                        or film.get("name")
                        or film_id
                    ),

                "runtime":
                    film.get(
                        "runtimeInMinutes"
                    ),

                "releaseDate":
                    film.get(
                        "releaseDate"
                    ),
            }
        )

        seen.add(
            film_id
        )

    return result


def truncate_visible(
    value: str,
    width: int,
) -> str:
    if len(value) <= width:
        return value

    if width <= 3:
        return value[:width]

    return (
        value[: width - 1]
        + "…"
    )


def choose_film(
    films: list[dict[str, Any]],
) -> dict[str, Any]:
    query = ""
    page = 0

    while True:
        visible = [
            film
            for film
            in films
            if (
                not query
                or query.lower()
                in film["title"].lower()
            )
        ]

        columns, rows = (
            terminal_size()
        )

        column_count = (
            2
            if columns >= 100
            else 1
        )

        display_rows = max(
            7,
            rows - 12,
        )

        page_capacity = max(
            1,
            display_rows
            * column_count,
        )

        pages = max(
            1,
            (
                len(visible)
                + page_capacity
                - 1
            )
            // page_capacity,
        )

        page = max(
            0,
            min(
                page,
                pages - 1,
            ),
        )

        start = (
            page
            * page_capacity
        )

        items = visible[
            start:
            start + page_capacity
        ]

        title(
            "Choose a film",
            f"{display_cinema_name()} "
            f"· {len(visible)} films "
            f"· page {page + 1}/{pages}",
        )

        print(
            DIM
            + "number = select · "
            + "/search = filter · "
            + "n/p = pages · "
            + "q = quit"
            + RESET
        )

        if query:
            print(
                f"{DIM}Filter:"
                f"{RESET} "
                f"{YELLOW}"
                f"{query}"
                f"{RESET}"
            )

        print()

        gap = 4

        cell_width = (
            max(
                30,
                columns - 4,
            )
            if column_count == 1
            else max(
                35,
                (
                    columns
                    - gap
                    - 2
                )
                // 2,
            )
        )

        cells = []

        for offset, film in enumerate(
            items
        ):
            number = (
                start
                + offset
                + 1
            )

            runtime = (
                f"{film['runtime']}m"
                if film.get(
                    "runtime"
                )
                else "?"
            )

            suffix = (
                f" · {runtime}"
            )

            prefix = (
                f"{number:>3}. "
            )

            max_title = max(
                8,
                cell_width
                - len(prefix)
                - len(suffix),
            )

            name = truncate_visible(
                film["title"],
                max_title,
            )

            formatted = (
                f"{CYAN}"
                f"{number:>3}."
                f"{RESET} "
                f"{BOLD}"
                f"{name}"
                f"{RESET}"
                f"{DIM}"
                f"{suffix}"
                f"{RESET}"
            )

            plain_len = (
                len(prefix)
                + len(name)
                + len(suffix)
            )

            cells.append(
                (
                    formatted,
                    max(
                        0,
                        cell_width
                        - plain_len,
                    ),
                )
            )

        if column_count == 1:
            for cell, _ in cells:
                print(
                    cell
                )

        else:
            left_count = min(
                display_rows,
                len(cells),
            )

            left = cells[
                :left_count
            ]

            right = cells[
                left_count:
            ]

            for row_index in range(
                max(
                    len(left),
                    len(right),
                )
            ):
                if (
                    row_index
                    < len(left)
                ):
                    left_text, left_pad = (
                        left[
                            row_index
                        ]
                    )

                    row = (
                        left_text
                        + " " * left_pad
                    )

                else:
                    row = (
                        " "
                        * cell_width
                    )

                if (
                    row_index
                    < len(right)
                ):
                    row += (
                        " " * gap                        + right[
                            row_index
                        ][0]
                    )

                print(
                    row
                )

        print()

        raw = prompt(
            "Film number, "
            "/search, n or p: "
        )

        lowered = (
            raw.lower()
        )

        if lowered in {
            "q",
            "quit",
            "exit",
        }:
            raise KeyboardInterrupt

        if lowered in {
            "n",
            "next",
        }:
            if (
                page + 1
                < pages
            ):
                page += 1

            continue

        if lowered in {
            "p",
            "prev",
            "previous",
        }:
            if page > 0:
                page -= 1

            continue

        if raw.startswith(
            "/"
        ):
            query = (
                raw[1:].strip()
            )

            page = 0
            continue

        try:
            number = int(
                raw
            )

        except ValueError:
            error(
                "Enter a film number, "
                "/search text, n, p or q."
            )

            time.sleep(
                0.5
            )

            continue

        if (
            1
            <= number
            <= len(visible)
        ):
            return (
                visible[
                    number - 1
                ]
            )

        error(
            "That film number "
            "is not in the list."
        )

        time.sleep(
            0.5
        )


def parse_dates(
    payload: dict[str, Any],
) -> list[str]:
    dates = set()

    for key in (
        "filmScreeningDates",
        "screeningDates",
        "dates",
    ):
        value = payload.get(
            key
        )

        if not isinstance(
            value,
            list,
        ):
            continue

        for item in value:
            if isinstance(
                item,
                str,
            ):
                dates.add(
                    item[:10]
                )

            elif isinstance(
                item,
                dict,
            ):
                for date_key in (
                    "businessDate",
                    "date",
                    "screeningDate",
                ):
                    date_value = (
                        item.get(
                            date_key
                        )
                    )

                    if isinstance(
                        date_value,
                        str,
                    ):
                        dates.add(
                            date_value[:10]
                        )

    business_date = payload.get(
        "businessDate"
    )

    if isinstance(
        business_date,
        str,
    ):
        dates.add(
            business_date[:10]
        )

    for showtime in find_list(
        payload,
        "showtimes",
    ):
        schedule = (
            showtime.get(
                "schedule"
            )
            or {}
        )

        business_date = (
            schedule.get(
                "businessDate"
            )
        )

        if isinstance(
            business_date,
            str,
        ):
            dates.add(
                business_date[:10]
            )

    return sorted(
        dates
    )


def date_label(
    value: str,
) -> str:
    try:
        return (
            datetime.fromisoformat(
                value
            ).strftime(
                "%A %d %B %Y"
            )
        )

    except Exception:
        return value


def choose_index(
    items: list[Any],
    label: str,
    allow_back=True,
) -> int | None:
    while True:
        raw = prompt(
            label
        )

        if (
            allow_back
            and raw.lower()
            in {
                "b",
                "back",
            }
        ):
            return None

        if raw.lower() in {
            "q",
            "quit",
            "exit",
        }:
            raise KeyboardInterrupt

        try:
            index = int(
                raw
            )

        except ValueError:
            error(
                "Enter a valid number."
            )

            continue

        if (
            1
            <= index
            <= len(items)
        ):
            return (
                index - 1
            )

        error(
            f"Choose between "
            f"1 and {len(items)}."
        )


def choose_date(
    dates: list[str],
    film: dict[str, Any],
) -> str | None:
    title(
        "Choose a date",
        display_cinema_name(),
    )

    selected_box(
        film=film["title"],
    )

    for index, value in enumerate(
        dates,
        1,
    ):
        print(
            f"{CYAN}"
            f"{index:>2}."
            f"{RESET} "
            f"{date_label(value)}"
        )

    print()

    print(
        DIM
        + "b = back · q = quit"
        + RESET
    )

    index = choose_index(
        dates,
        "Date: ",
    )

    return (
        None
        if index is None
        else dates[index]
    )


def parse_showtimes(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    result = []

    for showtime in find_list(
        payload,
        "showtimes",
    ):
        showtime_id = str(
            showtime.get("id")
            or showtime.get("ID")
            or ""
        )

        if not showtime_id:
            continue

        schedule = (
            showtime.get(
                "schedule"
            )
            or {}
        )

        result.append(
            {
                "id":
                    showtime_id,

                "startsAt":
                    schedule.get(
                        "startsAt"
                    )
                    or showtime.get(
                        "Showtime"
                    )
                    or showtime.get(
                        "startsAt"
                    )
                    or "",

                "businessDate":
                    schedule.get(
                        "businessDate"
                    ),

                "screenId":
                    showtime.get(
                        "screenId"
                    ),

                "seatLayoutId":
                    showtime.get(
                        "seatLayoutId"
                    ),

                "soldOut":
                    bool(
                        showtime.get(
                            "isSoldOut",
                            False,
                        )
                    ),
            }
        )

    result.sort(
        key=lambda item:
            item["startsAt"]
    )

    return result


def friendly_time(
    value: str,
) -> str:
    try:
        return (
            datetime.fromisoformat(
                value.replace(
                    "Z",
                    "+00:00",
                )
            ).strftime(
                "%H:%M"
            )
        )

    except Exception:
        return value


def choose_showtime(
    showtimes: list[dict[str, Any]],
    film: dict[str, Any],
    business_date: str,
) -> dict[str, Any] | None:
    usable = [
        item
        for item
        in showtimes
        if not item[
            "soldOut"
        ]
    ]

    title(
        "Choose a showtime",
        display_cinema_name(),
    )

    selected_box(
        film=film["title"],
        date=date_label(
            business_date
        ),
    )

    if not usable:
        warning(
            "No available showtimes."
        )

        wait_for_enter()

        return None

    for index, showtime in enumerate(
        usable,
        1,
    ):
        print(
            f"{CYAN}"
            f"{index:>2}."
            f"{RESET} "
            f"{BOLD}"
            f"{friendly_time(showtime['startsAt'])}"
            f"{RESET} "
            f"{DIM}"
            f"· Screen "
            f"{showtime.get('screenId') or '?'}"
            f"{RESET}"
        )

    print()

    print(
        DIM
        + "b = back · q = quit"
        + RESET
    )

    index = choose_index(
        usable,
        "Showtime: ",
    )

    return (
        None
        if index is None
        else usable[index]
    )


@dataclass
class Seat:
    seat_id: str
    label: str
    row_label: str
    area_name: str
    area_category_id: str
    area_number: int
    row_number: int
    column_number: int
    seat_type: str
    status: str = "Unknown"

    @property
    def available(
        self,
    ):
        return (
            self.status
            == "Available"
        )


def parse_layout(
    payload: dict[str, Any],
) -> dict[str, Seat]:
    seats = {}

    layout = (
        payload.get(
            "seatLayout"
        )
        or {}
    )

    for area in (
        layout.get(
            "areas"
        )
        or []
    ):
        if not isinstance(
            area,
            dict,
        ):
            continue

        area_name = text_value(
            area.get(
                "name"
            )
        )

        area_category_id = str(
            area.get(
                "areaCategoryId"
            )
            or ""
        )

        for row in (
            area.get(
                "rows"
            )
            or []
        ):
            if not isinstance(
                row,
                dict,
            ):
                continue

            for raw_seat in (
                row.get(
                    "seats"
                )
                or []
            ):
                if not isinstance(
                    raw_seat,
                    dict,
                ):
                    continue

                seat_id = (
                    raw_seat.get(
                        "id"
                    )
                )

                position = (
                    raw_seat.get(
                        "position"
                    )
                    or {}
                )

                if not isinstance(
                    seat_id,
                    str,
                ):
                    continue

                if not all(
                    isinstance(
                        position.get(
                            key
                        ),
                        int,
                    )
                    for key in (
                        "areaNumber",
                        "columnNumber",
                        "rowNumber",
                    )
                ):
                    continue

                seats[
                    seat_id
                ] = Seat(
                    seat_id=
                        seat_id,

                    label=
                        str(
                            raw_seat.get(
                                "label"
                            )
                            or "?"
                        ),

                    row_label=
                        str(
                            raw_seat.get(
                                "rowLabel"
                            )
                            or row.get(
                                "label"
                            )
                            or "?"
                        ),

                    area_name=
                        area_name,

                    area_category_id=
                        str(
                            raw_seat.get(
                                "areaCategoryId"
                            )
                            or area_category_id
                        ),

                    area_number=
                        position[
                            "areaNumber"
                        ],

                    row_number=
                        position[
                            "rowNumber"
                        ],

                    column_number=
                        position[
                            "columnNumber"
                        ],

                    seat_type=
                        str(
                            raw_seat.get(
                                "type"
                            )
                            or "Normal"
                        ),
                )

    return seats


def apply_availability(
    seats: dict[str, Seat],
    payload: dict[str, Any],
):
    for item in (
        payload.get(
            "seatAvailabilities"
        )
        or []
    ):
        if not isinstance(
            item,
            dict,
        ):
            continue

        seat_id = (
            item.get(
                "seatId"
            )
        )

        if seat_id in seats:
            seats[
                seat_id
            ].status = str(
                item.get(
                    "status"
                )
                or "Unknown"
            )


def rows_for_display(
    seats: dict[str, Seat],
):
    rows = {}

    for seat in seats.values():
        key = (
            seat.area_number,
            seat.row_number,
            seat.row_label,
        )

        rows.setdefault(
            key,
            [],
        ).append(
            seat
        )

    for row in rows.values():
        row.sort(
            key=lambda item:
                item.column_number
        )

    return dict(
        sorted(
            rows.items(),
            key=lambda item:
                (
                    item[0][0],
                    item[0][1],
                ),
        )
    )


def render_seat_map(
    seats: dict[str, Seat],
):
    print(
        DIM
        + "Legend: "
        + RESET
        + GREEN
        + "12"
        + RESET
        + " available · "
        + RED
        + "XX"
        + RESET
        + " unavailable · "
        + YELLOW
        + "--"
        + RESET
        + " other"
    )

    current_area = None

    for (
        area_number,
        _,
        row_label,
    ), row in rows_for_display(
        seats
    ).items():
        if (
            area_number
            != current_area
        ):
            current_area = (
                area_number
            )

            area_name = next(
                (
                    item.area_name
                    for item
                    in row
                    if item.area_name
                ),
                "",
            )

            print()

            print(
                BOLD
                + MAGENTA
                + (
                    area_name
                    or f"Area {area_number}"
                )
                + RESET
            )

        cells = []

        for seat in row:
            if (
                seat.status
                == "Available"
            ):
                cells.append(
                    GREEN
                    + f"{seat.label:>3}"
                    + RESET
                )

            elif seat.status in {
                "Sold",
                "Unavailable",
                "Held",
            }:
                cells.append(
                    RED
                    + " XX"
                    + RESET
                )

            else:
                cells.append(
                    YELLOW
                    + " --"
                    + RESET
                )

        print(
            f"{BOLD}"
            f"Row {row_label:>3}"
            f"{RESET} "
            + " ".join(
                cells
            )
        )


def build_seat_lookup(
    seats: dict[str, Seat],
):
    lookup = {}

    for seat in seats.values():
        lookup[
            seat.seat_id.lower()
        ] = seat

        lookup[
            f"{seat.row_label}"
            f"{seat.label}".lower()
        ] = seat

    return lookup


def expand_seat_input(
    raw: str,
) -> list[str]:
    result = []

    for chunk in raw.split(
        ","
    ):
        chunk = chunk.strip()

        if not chunk:
            continue

        match = re.fullmatch(
            r"([A-Za-z]+)"
            r"\s*(\d+)"
            r"\s*-\s*"
            r"(?:([A-Za-z]+)\s*)?"
            r"(\d+)",
            chunk,
        )

        if not match:
            result.append(
                chunk.upper()
            )

            continue

        start_row = (
            match.group(1).upper()
        )

        start_num = int(
            match.group(2)
        )

        end_row = (
            match.group(3)
            or start_row
        ).upper()

        end_num = int(
            match.group(4)
        )

        if (
            start_row
            != end_row
        ):
            raise ValueError(
                f"Range {chunk!r} "
                f"crosses rows."
            )

        if (
            end_num
            < start_num
        ):
            raise ValueError(
                f"Range {chunk!r} "
                f"runs backwards."
            )

        result.extend(
            f"{start_row}{number}"
            for number
            in range(
                start_num,
                end_num + 1,
            )
        )

    return result


def validate_selection(
    selected: list[Seat],
) -> tuple[bool, str]:
    if not selected:
        return (
            False,
            "Choose at least one seat.",
        )

    if (
        len(selected)
        > MAX_SEATS
    ):
        return (
            False,
            f"Maximum is {MAX_SEATS} seats.",
        )

    unavailable = [
        seat
        for seat
        in selected
        if not seat.available
    ]

    if unavailable:
        return (
            False,
            "Unavailable: "
            + ", ".join(
                f"{seat.row_label}"
                f"{seat.label}"
                for seat
                in unavailable
            ),
        )

    if len(
        {
            (
                seat.area_number,
                seat.row_number,
            )
            for seat
            in selected
        }
    ) != 1:
        return (
            False,
            "All seats must be "
            "in the same row.",
        )

    if len(
        {
            seat.area_category_id
            for seat
            in selected
        }
    ) != 1:
        return (
            False,
            "All seats must be "
            "in the same seating-price area.",
        )

    columns = sorted(
        seat.column_number
        for seat
        in selected
    )

    for left, right in zip(
        columns,
        columns[1:],
    ):
        if (
            right
            != left + 1
        ):
            return (
                False,
                "Seats must be next to "
                "each other with no gaps.",
            )

    return (
        True,
        "",
    )


def find_contiguous_blocks(
    seats: dict[str, Seat],
    max_block: int = MAX_SEATS,
) -> list[list[Seat]]:
    blocks = []
    
    for (area_number, row_number, row_label), row in rows_for_display(seats).items():
        current_block = []
        
        for seat in row:
            if seat.available:
                if not current_block:
                    current_block = [seat]
                else:
                    last_seat = current_block[-1]
                    if seat.column_number == last_seat.column_number + 1:
                        current_block.append(seat)
                    else:
                        if current_block:
                            for i in range(0, len(current_block), max_block):
                                chunk = current_block[i:i + max_block]
                                if len(chunk) > 0:
                                    blocks.append(chunk)
                        current_block = [seat]
            else:
                if current_block:
                    for i in range(0, len(current_block), max_block):
                        chunk = current_block[i:i + max_block]
                        if len(chunk) > 0:
                            blocks.append(chunk)
                    current_block = []
        
        if current_block:
            for i in range(0, len(current_block), max_block):
                chunk = current_block[i:i + max_block]
                if len(chunk) > 0:
                    blocks.append(chunk)
    
    return blocks


def group_seats_by_area(
    seats: list[Seat],
) -> dict[str, list[Seat]]:
    groups = {}
    for seat in seats:
        if seat.area_category_id not in groups:
            groups[seat.area_category_id] = []
        groups[seat.area_category_id].append(seat)
    return groups


def draw_pattern_on_seats(
    seats: dict[str, Seat],
    pattern: str,
) -> list[list[Seat]]:
    pattern = pattern.lower()
    blocks = []
    
    if pattern == "rude" or pattern == "willy" or pattern == "dick" or pattern == "penis" or pattern == "cock":
        rows = list(rows_for_display(seats).values())
        if len(rows) >= 5:
            middle_row_idx = len(rows) // 2
            middle_col_idx = max(1, len(rows[middle_row_idx]) // 2)
            
            shape_seats = []
            
            for i in range(3):
                if middle_row_idx - i >= 0:
                    row = rows[middle_row_idx - i]
                    if 0 <= middle_col_idx - 1 - i < len(row):
                        seat = row[middle_col_idx - 1 - i]
                        if seat.available:
                            shape_seats.append(seat)
                    if 0 <= middle_col_idx + i < len(row):
                        seat = row[middle_col_idx + i]
                        if seat.available:
                            shape_seats.append(seat)
            
            for i in range(1, 5):
                if middle_row_idx + i < len(rows):
                    row = rows[middle_row_idx + i]
                    col_offset = 1 if i > 2 else 0
                    if 0 <= middle_col_idx - col_offset < len(row):
                        seat = row[middle_col_idx - col_offset]
                        if seat.available:
                            shape_seats.append(seat)
                    if 0 <= middle_col_idx + col_offset < len(row) and col_offset > 0:
                        seat = row[middle_col_idx + col_offset]
                        if seat.available:
                            shape_seats.append(seat)
            
            for i in range(0, len(shape_seats), MAX_SEATS):
                block = shape_seats[i:i + MAX_SEATS]
                if len(block) >= 2:
                    blocks.append(block)
    
    return blocks


def choose_booking_mode() -> tuple[str, int | None, bool]:
    title(
        "Booking mode",
        "How would you like to book?",
    )
    
    print()
    print(f"{CYAN}1.{RESET} Book specific seats (manual selection)")
    print(f"{CYAN}2.{RESET} Book a specific number of seats (auto-select contiguous)")
    print(f"{CYAN}3.{RESET} Book ALL available seats (auto-book with adult tickets)")
    print(f"{CYAN}4.{RESET} Draw a pattern (e.g., rude)")
    print()
    
    while True:
        choice = prompt("Choice: ")
        
        if choice == "1":
            return "manual", None, False
        elif choice == "2":
            while True:
                try:
                    num = int(prompt("How many seats? "))
                    if num > 0:
                        return "specific", num, False
                    error("Number must be positive.")
                except ValueError:
                    error("Enter a valid number.")
        elif choice == "3":
            return "all", None, True
        elif choice == "4":
            return "pattern", None, False
        else:
            error("Choose 1, 2, 3 or 4.")


def auto_select_seats(
    seats: dict[str, Seat],
    count: int,
) -> list[Seat] | None:
    blocks = find_contiguous_blocks(seats)
    
    for block in blocks:
        if len(block) == count:
            return block
    
    for block in blocks:
        if len(block) > count:
            return block[:count]
    
    for row_key, row in rows_for_display(seats).items():
        row_blocks = [b for b in blocks if b[0].row_label == row[0].row_label]
        combined = []
        for block in row_blocks:
            combined.extend(block)
            if len(combined) >= count:
                return combined[:count]
    
    error(f"Could not find {count} contiguous available seats.")
    return None


def book_single_group(
    api: OdeonAPI,
    group_info: dict,
    showtime_id: str,
    film: dict,
    business_date: str,
    showtime: dict,
    auto_ticket: bool,
    ticket_cache: dict,
    idx: int,
    total_orders: int,
    results: list,
):
    group = group_info['seats']
    area_name = group_info['area_name']
    area_id = group_info['area_id']
    
    seat_ids = [seat.seat_id for seat in group]
    seat_labels = ", ".join(f"{seat.row_label}{seat.label}" for seat in group)
    
    try:
        if auto_ticket and area_id in ticket_cache and ticket_cache[area_id]:
            ticket_type_id = ticket_cache[area_id]
        else:
            price_payload = api.ticket_prices(showtime_id)
            ticket_type_id = choose_ticket_type(
                price_payload,
                film,
                business_date,
                showtime,
                group,
            )
        
        if ticket_type_id is None:
            results.append({'idx': idx, 'success': False, 'error': 'No ticket type selected'})
            return
        
        try:
            revalidate_live_selection(api, showtime_id, group)
        except RuntimeError as exc:
            results.append({'idx': idx, 'success': False, 'error': str(exc), 'seats': seat_labels})
            return
        
        order_payload = api.create_order()
        order_id = get_order_id(order_payload)
        
        tickets = [{"id": str(uuid.uuid4()), "ticketTypeId": ticket_type_id} for _ in seat_ids]
        api.set_showtime(order_id, showtime_id, seat_ids, tickets)
        
        results.append({'idx': idx, 'success': True, 'order_id': order_id, 'seats': seat_labels, 'area': area_name})
    except Exception as exc:
        results.append({'idx': idx, 'success': False, 'error': str(exc), 'seats': seat_labels})


def book_seats_in_groups(
    api: OdeonAPI,
    selected_seats: list[Seat],
    showtime_id: str,
    film: dict,
    business_date: str,
    showtime: dict,
    auto_ticket: bool = False,
    max_workers: int = 5,
) -> bool:
    area_groups = group_seats_by_area(selected_seats)
    
    info(f"Found {len(area_groups)} different price areas.")
    for area_id, seats in area_groups.items():
        area_name = seats[0].area_name if seats else "Unknown"
        info(f"  {area_name}: {len(seats)} seats")
    
    print()
    
    all_groups = []
    total_orders = 0
    
    for area_id, seats in area_groups.items():
        for i in range(0, len(seats), MAX_SEATS):
            chunk = seats[i:i + MAX_SEATS]
            if chunk:
                all_groups.append({
                    'seats': chunk,
                    'area_id': area_id,
                    'area_name': chunk[0].area_name
                })
                total_orders += 1
    
    info(f"Will create {total_orders} reservations across {len(area_groups)} price areas.")
    print()
    
    ticket_cache = {}
    if auto_ticket:
        info("Auto-booking mode: Using first available adult ticket type.")
        print()
        price_payload = api.ticket_prices(showtime_id)
        
        for group_info in all_groups:
            area_id = group_info['area_id']
            if area_id not in ticket_cache:
                prices = allowed_ticket_prices(price_payload, area_id)
                if prices:
                    ticket_cache[area_id] = str(prices[0]['ticketTypeId'])
                else:
                    ticket_cache[area_id] = None
        
        for area_id, ticket_id in ticket_cache.items():
            if ticket_id:
                area_name = next((g['area_name'] for g in all_groups if g['area_id'] == area_id), "Unknown")
                metadata = ticket_type_metadata(price_payload)
                meta = metadata.get(ticket_id, {})
                desc = text_value(meta.get('description')) or "Adult"
                info(f"  {area_name}: using {desc}")
        print()
        
        confirm = prompt("Book all seats with these ticket types? [Y/n]: ").lower()
        if confirm not in {"", "y", "yes"}:
            return False
    else:
        confirm = prompt("Continue? [Y/n]: ").lower()
        if confirm not in {"", "y", "yes"}:
            return False
    
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for idx, group_info in enumerate(all_groups, 1):
            future = executor.submit(
                book_single_group,
                api,
                group_info,
                showtime_id,
                film,
                business_date,
                showtime,
                auto_ticket,
                ticket_cache,
                idx,
                total_orders,
                results
            )
            futures.append(future)
        
        for future in as_completed(futures):
            pass
    
    results.sort(key=lambda x: x['idx'])
    
    success_count = 0
    failed_seats = []
    
    for result in results:
        if result['success']:
            title(
                f"Reservation {result['idx']}/{total_orders}",
                f"Booking seats in {result['area']}",
            )
            success(f"Reservation {result['idx']} created successfully! Order ID: {result['order_id']}")
            success_count += 1
        else:
            title(
                f"Reservation {result['idx']}/{total_orders}",
                f"Booking seats in {result.get('area', 'Unknown')}",
            )
            if 'seats' in result:
                error(f"Failed to book: {result['seats']}")
                failed_seats.append(result['seats'])
            else:
                error(f"Failed: {result.get('error', 'Unknown error')}")
    
    if failed_seats:
        info(f"Failed seats: {', '.join(failed_seats)}")
    
    info(f"Completed {success_count}/{total_orders} reservations.")
    return success_count > 0


def choose_seats(
    seats: dict[str, Seat],
    film: dict[str, Any],
    business_date: str,
    showtime: dict[str, Any],
) -> tuple[list[Seat] | None, bool]:
    lookup = build_seat_lookup(seats)
    
    mode, specific_count, auto_ticket = choose_booking_mode()
    
    if mode == "manual":
        return choose_seats_manual(seats, film, business_date, showtime), auto_ticket
    
    elif mode == "specific" and specific_count:
        title(
            f"Auto-selecting {specific_count} seats",
            "Finding contiguous seats...",
        )
        
        selected = auto_select_seats(seats, specific_count)
        if selected:
            render_seat_map(seats)
            print()
            seat_labels = ", ".join(f"{seat.row_label}{seat.label}" for seat in selected)
            info(f"Selected: {seat_labels}")
            print()
            confirm = prompt("Use these seats? [Y/n]: ").lower()
            if confirm in {"", "y", "yes"}:
                return selected, auto_ticket
        return None, auto_ticket
    
    elif mode == "all":
        blocks = find_contiguous_blocks(seats)
        all_seats = []
        for block in blocks:
            all_seats.extend(block)
        
        if all_seats:
            total = len(all_seats)
            area_groups = group_seats_by_area(all_seats)
            info(f"Found {total} available seats across {len(blocks)} blocks.")
            info(f"Seats by price area:")
            for area_id, area_seats in area_groups.items():
                area_name = area_seats[0].area_name if area_seats else "Unknown"
                info(f"  {area_name}: {len(area_seats)} seats")
            
            if auto_ticket:
                info("Auto-booking mode: Will use adult tickets for all seats.")
            print()
            render_seat_map(seats)
            print()
            confirm = prompt(f"Book all {total} seats? [Y/n]: ").lower()
            if confirm in {"", "y", "yes"}:
                return all_seats, auto_ticket
        else:
            error("No available seats found.")
        return None, auto_ticket
    
    elif mode == "pattern":
        title(
            "Draw a pattern",
            "What pattern would you like to draw?",
        )
        print()
        print("Available patterns:")
        print(f"  {CYAN}rude{RESET} - Draw a rude shape")
        print()
        
        pattern = prompt("Pattern: ").lower()
        selected = draw_pattern_on_seats(seats, pattern)
        
        if selected:
            all_seats = []
            for block in selected:
                all_seats.extend(block)
            
            if all_seats:
                area_pattern_groups = group_seats_by_area(all_seats)
                info(f"Pattern uses {len(all_seats)} seats across {len(area_pattern_groups)} price areas.")
                for area_id, area_seats in area_pattern_groups.items():
                    area_name = area_seats[0].area_name if area_seats else "Unknown"
                    info(f"  {area_name}: {len(area_seats)} seats")
                print()
                render_seat_map(seats)
                print()
                confirm = prompt("Use these seats? [Y/n]: ").lower()
                if confirm in {"", "y", "yes"}:
                    return all_seats, auto_ticket
        else:
            error("Could not draw that pattern with available seats.")
        return None, auto_ticket


def choose_seats_manual(
    seats: dict[str, Seat],
    film: dict[str, Any],
    business_date: str,
    showtime: dict[str, Any],
) -> list[Seat] | None:
    lookup = build_seat_lookup(seats)
    
    while True:
        title(
            "Choose your seats",
            f"{display_cinema_name()} "
            f"· max {MAX_SEATS}",
        )

        selected_box(
            film=film["title"],
            date=date_label(
                business_date
            ),
            showtime=friendly_time(
                showtime[
                    "startsAt"
                ]
            ),
        )

        render_seat_map(
            seats
        )

        print()

        print(
            DIM
            + "Examples: "
            + "C1-4, C1-C4, "
            + "C1,C2,C3,C4"
            + RESET
        )

        print(
            DIM
            + "b = back · q = quit"
            + RESET
        )

        raw = prompt(
            f"Seats (1-{MAX_SEATS}): "
        )

        if raw.lower() in {
            "b",
            "back",
        }:
            return None

        if raw.lower() in {
            "q",
            "quit",
            "exit",
        }:
            raise KeyboardInterrupt

        try:
            values = [
                value.lower()
                for value
                in expand_seat_input(
                    raw
                )
            ]

        except ValueError as exc:
            error(
                str(exc)
            )

            time.sleep(
                0.7
            )

            continue

        if (
            len(values)
            > MAX_SEATS
        ):
            error(
                f"Maximum is {MAX_SEATS} seats. "
                f"Your input expands to "
                f"{len(values)}."
            )

            time.sleep(
                0.8
            )

            continue

        chosen = []
        unknown = []

        for value in values:
            seat = lookup.get(
                value
            )

            if seat is None:
                unknown.append(
                    value
                )

            elif seat not in chosen:
                chosen.append(
                    seat
                )

        if unknown:
            error(
                "Unknown seat(s): "
                + ", ".join(
                    unknown
                )
            )

            time.sleep(
                0.8
            )

            continue

        valid, reason = (
            validate_selection(
                chosen
            )
        )

        if not valid:
            error(
                reason
            )

            time.sleep(
                0.8
            )

            continue

        chosen.sort(
            key=lambda item:
                item.column_number
        )

        return chosen


def revalidate_live_selection(
    api: OdeonAPI,
    showtime_id: str,
    chosen: list[Seat],
):
    payload = (
        api.seat_availability_with_retry(
            showtime_id
        )
    )

    statuses = {
        str(
            item.get(
                "seatId"
            )
        ):
            str(
                item.get(
                    "status"
                )
            )

        for item
        in (
            payload.get(
                "seatAvailabilities"
            )
            or []
        )

        if isinstance(
            item,
            dict,
        )
    }

    unavailable = [
        seat
        for seat
        in chosen
        if statuses.get(
            seat.seat_id
        )
        != "Available"
    ]

    if unavailable:
        raise RuntimeError(
            "Seats became unavailable: "
            + ", ".join(
                f"{seat.row_label}"
                f"{seat.label}"
                for seat
                in unavailable
            )
        )


def ticket_type_metadata(
    payload: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    related = (
        payload.get(
            "relatedData"
        )
        or {}
    )

    result = {}

    for item in (
        related.get(
            "ticketTypes"
        )
        or []
    ):
        if (
            isinstance(
                item,
                dict,
            )
            and item.get(
                "id"
            )
        ):
            result[
                str(
                    item["id"]
                )
            ] = item

    return result


def allowed_ticket_prices(
    payload: dict[str, Any],
    area_category_id: str | None = None,
):
    metadata = (
        ticket_type_metadata(
            payload
        )
    )

    result = []
    seen = set()

    for price in (
        payload.get(
            "ticketPrices"
        )
        or []
    ):
        if not isinstance(
            price,
            dict,
        ):
            continue

        if price.get(
            "restrictions"
        ):
            continue

        if not price.get(
            "isDefault",
            True,
        ):
            continue

        ticket_id = str(
            price.get(
                "ticketTypeId"
            )
            or ""
        )

        if (
            not ticket_id
            or ticket_id
            in seen
        ):
            continue

        meta = (
            metadata.get(
                ticket_id,
                {},
            )
        )

        if (
            area_category_id
            and meta.get(
                "areaCategoryId"
            )
            != area_category_id
        ):
            continue

        if (
            meta
            and meta.get(
                "type"
            )
            not in {
                None,
                "Normal",
            }
        ):
            continue

        result.append(
            price
        )

        seen.add(
            ticket_id
        )

    return result


def selected_area(
    chosen: list[Seat],
) -> tuple[str, str]:
    ids = {
        seat.area_category_id
        for seat
        in chosen
    }

    if len(ids) != 1:
        raise RuntimeError(
            "Selected seats span "
            "multiple price areas."
        )

    names = {
        seat.area_name
        for seat
        in chosen
        if seat.area_name
    }

    return (
        next(
            iter(ids)
        ),
        (
            next(
                iter(names)
            )
            if names
            else "Seating Area"
        ),
    )


def choose_ticket_type(
    payload: dict[str, Any],
    film: dict[str, Any],
    business_date: str,
    showtime: dict[str, Any],
    chosen: list[Seat],
) -> str | None:
    area_ids = {seat.area_category_id for seat in chosen}
    
    if len(area_ids) > 1:
        title(
            "Multiple price areas detected",
            f"{len(area_ids)} different areas",
        )
        
        selected_box(
            film=film["title"],
            date=date_label(business_date),
            showtime=friendly_time(showtime["startsAt"]),
            seats=", ".join(f"{seat.row_label}{seat.label}" for seat in chosen),
        )
        
        print()
        warning("Your selected seats span multiple price areas.")
        print()
        
        for area_id in area_ids:
            area_seats = [s for s in chosen if s.area_category_id == area_id]
            area_name = area_seats[0].area_name if area_seats else "Unknown"
            seats_str = ", ".join(f"{s.row_label}{s.label}" for s in area_seats)
            info(f"  {area_name}: {seats_str}")
        
        print()
        print("Options:")
        print(f"  {CYAN}1{RESET} - Book all seats as multiple reservations (recommended)")
        print(f"  {CYAN}2{RESET} - Choose one price area only")
        print(f"  {CYAN}3{RESET} - Go back and choose different seats")
        print()
        
        while True:
            choice = prompt("Choice: ").strip()
            if choice == "1":
                return "MULTI_AREA"
            elif choice == "2":
                area_list = list(area_ids)
                print()
                for idx, area_id in enumerate(area_list, 1):
                    area_seats = [s for s in chosen if s.area_category_id == area_id]
                    area_name = area_seats[0].area_name if area_seats else "Unknown"
                    print(f"  {CYAN}{idx}{RESET} - {area_name} ({len(area_seats)} seats)")
                print()
                
                try:
                    area_choice = int(prompt("Choose area number: "))
                    if 1 <= area_choice <= len(area_list):
                        selected_area_id = area_list[area_choice - 1]
                        filtered_chosen = [s for s in chosen if s.area_category_id == selected_area_id]
                        return choose_ticket_type(payload, film, business_date, showtime, filtered_chosen)
                except ValueError:
                    pass
                error("Invalid choice.")
                continue
            elif choice == "3":
                return None
            else:
                error("Choose 1, 2 or 3.")
    
    area_id, area_name = selected_area(chosen)
    
    prices = allowed_ticket_prices(payload, area_id)
    metadata = ticket_type_metadata(payload)
    
    if not prices:
        raise RuntimeError(
            "No unrestricted ticket types "
            f"returned for {area_name}."
        )
    
    title(
        "Choose ticket type",
        f"{display_cinema_name()} "
        f"· {area_name}",
    )
    
    selected_box(
        film=film["title"],
        date=date_label(business_date),
        showtime=friendly_time(showtime["startsAt"]),
        seats=", ".join(
            f"{seat.row_label}"
            f"{seat.label}"
            for seat
            in chosen
        ),
    )
    
    for index, price in enumerate(
        prices,
        1,
    ):
        ticket_id = str(
            price.get(
                "ticketTypeId"
            )
            or ""
        )
    
        meta = (
            metadata.get(
                ticket_id,
                {},
            )
        )
    
        description = (
            text_value(
                meta.get(
                    "description"
                )
            )
            or "Ticket"
        )
    
        amount = (
            price.get(
                "price"
            )
            or {}
        ).get(
            "valueIncludingTax"
        )
    
        fee = (
            price.get(
                "bookingFee"
            )
            or {}
        ).get(
            "amountIncludingTax"
        )
    
        try:
            total = (
                float(amount)
                + float(
                    fee
                    or 0
                )
            )
    
            total_text = (
                f"£{total:.2f}"
            )
    
        except Exception:
            total_text = "?"
    
        print(
            f"{CYAN}"
            f"{index:>2}."
            f"{RESET} "
            f"{BOLD}"
            f"{description:<20}"
            f"{RESET} "
            f"{GREEN}"
            f"{BOLD}"
            f"{total_text} each"
            f"{RESET}"
        )
    
    print()
    
    print(
        DIM
        + f"Prices shown for "
        + f"{area_name} only."
        + RESET
    )
    
    print(
        DIM
        + "b = back · q = quit"
        + RESET
    )
    
    index = choose_index(
        prices,
        "Ticket: ",
    )
    
    return (
        None
        if index is None
        else str(
            prices[
                index
            ][
                "ticketTypeId"
            ]
        )
    )


def estimated_total(
    payload: dict[str, Any],
    ticket_type_id: str,
    count: int,
) -> float | None:
    for price in (
        payload.get(
            "ticketPrices"
        )
        or []
    ):
        if (
            price.get(
                "ticketTypeId"
            )
            != ticket_type_id
        ):
            continue

        amount = (
            price.get(
                "price"
            )
            or {}
        ).get(
            "valueIncludingTax"
        )

        fee = (
            price.get(
                "bookingFee"
            )
            or {}
        ).get(
            "amountIncludingTax"
        )

        try:
            return (
                (
                    float(amount)
                    + float(
                        fee
                        or 0
                    )
                )
                * count
            )

        except Exception:
            return None

    return None


def final_confirmation(
    film: dict[str, Any],
    business_date: str,
    showtime: dict[str, Any],
    chosen: list[Seat],
    ticket_type_id: str,
    price_payload: dict[str, Any],
) -> bool:
    _, area_name = (
        selected_area(
            chosen
        )
    )

    total = (
        estimated_total(
            price_payload,
            ticket_type_id,
            len(chosen),
        )
    )

    title(
        "Confirm reservation",
        "Nothing has been reserved yet",
    )

    print()

    rows = [
        (
            "Cinema",
            display_cinema_name(),
        ),
        (
            "Film",
            film["title"],
        ),
        (
            "Date",
            date_label(
                business_date
            ),
        ),
        (
            "Time",
            friendly_time(
                showtime[
                    "startsAt"
                ]
            ),
        ),
        (
            "Screen",
            str(
                showtime.get(
                    "screenId"
                )
                or "?"
            ),
        ),
        (
            "Seats",
            ", ".join(
                f"{seat.row_label}"
                f"{seat.label}"
                for seat
                in chosen
            ),
        ),
        (
            "Seat area",
            area_name,
        ),
        (
            "Quantity",
            str(
                len(chosen)
            ),
        ),
    ]

    if total is not None:
        rows.append(
            (
                "Estimated total",
                f"£{total:.2f}",
            )
        )

    for label, value in rows:
        print(
            f"{DIM}"
            f"{label:<16}"
            f"{RESET}"
            f"{BOLD}"
            f"{value}"
            f"{RESET}"
        )

    print()

    warning(
        "Seats can still be taken "
        "before the reservation request completes."
    )

    print()

    print(
        f"{GREEN}"
        f"{BOLD}"
        f"Y"
        f"{RESET} = reserve   "
        f"{YELLOW}"
        f"{BOLD}"
        f"B"
        f"{RESET} = back   "
        f"{RED}"
        f"{BOLD}"
        f"Q"
        f"{RESET} = quit"
    )

    while True:
        choice = prompt(
            "Confirm [Y/b/q]: "
        ).lower()

        if choice in {
            "",
            "y",
            "yes",
        }:
            return True

        if choice in {
            "b",
            "back",
        }:
            return False

        if choice in {
            "q",
            "quit",
            "exit",
        }:
            raise KeyboardInterrupt

        error(
            "Choose Y, B or Q."
        )


def get_order(
    payload: dict[str, Any],
) -> dict[str, Any]:
    order = payload.get(
        "order"
    )

    return (
        order
        if isinstance(
            order,
            dict,
        )
        else payload
    )


def get_order_id(
    payload: dict[str, Any],
) -> str:
    order = get_order(
        payload
    )

    order_id = order.get(
        "id"
    )

    if not order_id:
        raise RuntimeError(
            "Order ID missing from "
            "create-order response."
        )

    return str(
        order_id
    )


def reservation_result(
    payload: dict[str, Any],
):
    order = get_order(
        payload
    )

    title(
        "Reservation created",
        display_cinema_name(),
    )

    success(
        "Seats and ticket types "
        "were attached to the order."
    )

    print()

    print(
        f"{DIM}"
        f"{'Order ID':<14}"
        f"{RESET}"
        f"{BOLD}"
        f"{order.get('id', '?')}"
        f"{RESET}"
    )

    print(
        f"{DIM}"
        f"{'Status':<14}"
        f"{RESET}"
        f"{BOLD}"
        f"{order.get('status', '?')}"
        f"{RESET}"
    )

    total = (
        order.get(
            "totalPrice"
        )
        or {}
    ).get(
        "valueIncludingTax"
    )

    if total is not None:
        print(
            f"{DIM}"
            f"{'Total':<14}"
            f"{RESET}"
            f"{GREEN}"
            f"{BOLD}"
            f"£{total}"
            f"{RESET}"
        )

    expiry = order.get(
        "expiresAt"
    )

    if expiry:
        print(
            f"{DIM}"
            f"{'Expires':<14}"
            f"{RESET}"
            f"{expiry}"
        )

    print()

    print(
        DIM
        + "Detailed log:"
        + RESET
    )

    print(
        LOG_PATH.resolve()
    )

    print()


def load_dates(
    api: OdeonAPI,
    film_id: str,
) -> list[str]:
    dates = parse_dates(
        api.screening_dates(
            film_id
        )
    )

    if dates:
        return dates

    return parse_dates(
        api.first_showtimes(
            film_id
        )
    )


def main() -> int:
    global SITE_ID
    global SITE_NAME

    title(
        "Welcome",
        "ODEON UK",
    )

    print()

    print(
        f"  {CYAN}1.{RESET} Cinema"
    )

    print(
        f"  {CYAN}2.{RESET} Film"
    )

    print(
        f"  {CYAN}3.{RESET} Date"
    )

    print(
        f"  {CYAN}4.{RESET} Showtime"
    )

    print(
        f"  {CYAN}5.{RESET} Seats"
    )

    print(
        f"  {CYAN}6.{RESET} Ticket type"
    )

    print(
        f"  {CYAN}7.{RESET} Confirmation"
    )

    print()

    timeout_raw = prompt(
        f"HTTP timeout "
        f"[{DEFAULT_TIMEOUT}]: "
    )

    try:
        timeout = int(
            timeout_raw
            or DEFAULT_TIMEOUT
        )

    except ValueError:
        timeout = (
            DEFAULT_TIMEOUT
        )

    api = OdeonAPI(
        "",
        timeout,
    )

    SITE_ID, SITE_NAME = (
        choose_cinema(
            api
        )
    )

    api.site_id = (
        SITE_ID
    )

    LOGGER.info(
        "Cinema selected: %s (%s)",
        display_cinema_name(),
        display_site_id(),
    )

    title(
        "Loading films",
        display_cinema_name(),
    )

    info(
        "Fetching cinema programme..."
    )

    films = parse_films(
        api.films_for_site()
    )

    if not films:
        raise RuntimeError(
            "No films returned."
        )

    while True:
        film = choose_film(
            films
        )

        LOGGER.info(
            "Film selected: %s (%s)",
            film["title"],
            film["id"],
        )

        dates = load_dates(
            api,
            film["id"],
        )

        if not dates:
            title(
                "No dates found",
                film["title"],
            )

            warning(
                "No screening dates "
                "were returned."
            )

            wait_for_enter(
                "Press Enter to "
                "choose another film..."
            )

            continue

        business_date = (
            choose_date(
                dates,
                film,
            )
        )

        if business_date is None:
            continue

        while True:
            title(
                "Loading showtimes",
                date_label(
                    business_date
                ),
            )

            info(
                "Fetching sessions..."
            )

            showtimes = (
                parse_showtimes(
                    api.showtimes_for_date(
                        film["id"],
                        business_date,
                    )
                )
            )

            if not showtimes:
                warning(
                    "No showtimes returned "
                    "for that date."
                )

                wait_for_enter()

                break

            showtime = (
                choose_showtime(
                    showtimes,
                    film,
                    business_date,
                )
            )

            if showtime is None:
                new_date = (
                    choose_date(
                        dates,
                        film,
                    )
                )

                if new_date is None:
                    break

                business_date = (
                    new_date
                )

                continue

            showtime_id = (
                showtime["id"]
            )

            seat_layout_id = (
                showtime.get(
                    "seatLayoutId"
                )
            )

            if not seat_layout_id:
                error(
                    "This showtime did not "
                    "return a seat layout."
                )

                wait_for_enter()

                continue

            title(
                "Loading seat map",
                f"{film['title']} "
                f"· "
                f"{friendly_time(showtime['startsAt'])}",
            )

            info(
                "Loading layout..."
            )

            try:
                layout_payload = (
                    api.seat_layout(
                        str(
                            seat_layout_id
                        )
                    )
                )

                info(
                    "Checking live availability..."
                )

                availability_payload = (
                    api.seat_availability_with_retry(
                        showtime_id
                    )
                )

            except ApiError as exc:
                if (
                    exc.status_code
                    == 403
                ):
                    title(
                        "Seat map unavailable",
                        f"{film['title']} "
                        f"· "
                        f"{friendly_time(showtime['startsAt'])}",
                    )

                    error(
                        "The seat-availability "
                        "request returned "
                        "HTTP 403 twice."
                    )

                    warning(
                        "No reservation request "
                        "was made."
                    )

                    wait_for_enter(
                        "Press Enter to choose "
                        "another showtime..."
                    )

                    continue

                raise

            seats = parse_layout(
                layout_payload
            )

            if not seats:
                error(
                    "Could not parse "
                    "the seat layout."
                )

                wait_for_enter()

                continue

            apply_availability(
                seats,
                availability_payload,
            )

            chosen, auto_ticket = choose_seats(
                seats,
                film,
                business_date,
                showtime,
            )

            if chosen is None:
                continue

            seat_ids = [
                seat.seat_id
                for seat
                in chosen
            ]

            title(
                "Loading ticket types",
                film["title"],
            )

            info(
                "Fetching ticket prices..."
            )

            price_payload = (
                api.ticket_prices(
                    showtime_id
                )
            )

            ticket_type_id = (
                choose_ticket_type(
                    price_payload,
                    film,
                    business_date,
                    showtime,
                    chosen,
                )
            )

            if ticket_type_id is None:
                continue

            if ticket_type_id == "MULTI_AREA":
                if book_seats_in_groups(api, chosen, showtime_id, film, business_date, showtime, auto_ticket):
                    wait_for_enter("Press Enter to exit...")
                    return 0
                else:
                    continue

            if not final_confirmation(
                film,
                business_date,
                showtime,
                chosen,
                ticket_type_id,
                price_payload,
            ):
                continue

            title(
                "Final availability check",
                "No order created yet",
            )

            info(
                "Re-checking selected seats..."
            )

            revalidate_live_selection(
                api,
                showtime_id,
                chosen,
            )

            success(
                "Seats are still available."
            )

            print()

            info(
                "Creating order..."
            )

            order_payload = (
                api.create_order()
            )

            order_id = get_order_id(
                order_payload
            )

            success(
                "Order created."
            )

            print()

            info(
                "Reserving seats..."
            )

            try:
                api.set_showtime(
                    order_id,
                    showtime_id,
                    seat_ids,
                    [],
                )

            except ApiError as exc:
                if (
                    exc.status_code
                    == 400
                    and isinstance(
                        exc.payload,
                        dict,
                    )
                    and exc.payload.get(
                        "title"
                    )
                    == "Seats unavailable"
                ):
                    title(
                        "Reservation failed",
                        film["title"],
                    )

                    error(
                        "Those seats "
                        "became unavailable."
                    )

                    wait_for_enter(
                        "Press Enter to choose "
                        "another block..."
                    )

                    continue

                raise

            success(
                "Seats reserved."
            )

            tickets = [
                {
                    "id":
                        str(
                            uuid.uuid4()
                        ),

                    "ticketTypeId":
                        ticket_type_id,
                }
                for _
                in seat_ids
            ]

            print()

            info(
                "Attaching ticket types..."
            )

            ticket_payload = (
                api.set_showtime(
                    order_id,
                    showtime_id,
                    seat_ids,
                    tickets,
                )
            )

            success(
                "Ticket types attached."
            )

            LOGGER.info(
                "Reservation flow completed"
            )

            reservation_result(
                ticket_payload
            )

            wait_for_enter(
                "Press Enter to exit..."
            )

            return 0


if __name__ == "__main__":
    try:
        raise SystemExit(
            main()
        )

    except KeyboardInterrupt:
        LOGGER.info(
            "User cancelled"
        )

        title(
            "Cancelled",
            "No further requests will be made",
        )

        warning(
            "User cancelled."
        )

        print()

        print(
            DIM
            + "Log: "
            + str(
                LOG_PATH.resolve()
            )
            + RESET
        )

        raise SystemExit(
            130
        )

    except Exception as exc:
        LOGGER.error(
            "FLOW FAILED: %s",
            private_string(
                str(exc)
            ),
        )

        LOGGER.debug(
            "Full traceback:\n%s",
            private_string(
                traceback.format_exc()
            ),
        )

        title(
            "Something went wrong",
            display_cinema_name(),
        )

        error(
            private_string(
                str(exc)
            )
        )

        print()

        print(
            DIM
            + "Detailed error log:"
            + RESET
        )

        print(
            LOG_PATH.resolve()
        )

        print()

        raise SystemExit(
            1
        )