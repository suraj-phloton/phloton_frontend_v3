import json
import time
import streamlit as st
import pandas as pd
import pytz


class Anedya:
    def __init__(self) -> None:
        pass

    def new_client(self, API_KEY):
        return NewClient(API_KEY)

    def new_node(self, new_client, nodeId: str):
        return NewNode(new_client, nodeId)


class NewClient:
    def __init__(self, API_KEY) -> None:
        if API_KEY == "":
            st.error("Please config a valid NODE ID and API key.")
        elif API_KEY == "":
            st.error("Please config a valid API key.")
        else:
            self.API_KEY = API_KEY


class NewNode:
    def __init__(self, new_client: NewClient, nodeId: str) -> None:
        self.nodeId = nodeId
        self.API_KEY = new_client.API_KEY

    def get_deviceStatus(self) -> dict:
        return anedya_getDeviceStatus(self.API_KEY, self.nodeId)

    def get_latestData(self, variable_identifier: str) -> dict:
        return get_latestData(variable_identifier, self.nodeId, self.API_KEY)

    def get_data(
        self, variable_identifier: str, from_time: int, to_time: int
    ) -> pd.DataFrame:
        return get_data(
            variable_identifier, self.nodeId, from_time, to_time, self.API_KEY
        )

    def get_data_paginated(
        self,
        variable_identifier: str,
        from_time: int,
        to_time: int,
        chunk_days: int = 1,
    ) -> pd.DataFrame:
        """
        Fetches ALL data across a date range by splitting into daily chunks.
        Use this instead of get_data() for ranges longer than ~1 day, to avoid
        Anedya's silent row truncation at ~10k-20k rows per request.
        """
        return get_data_paginated(
            variable_identifier, self.nodeId, from_time, to_time, self.API_KEY, chunk_days
        )

    def get_valueStore(self, scope: str = "node", id: str = "", key: str = "") -> dict:
        return anedya_getValueStore(self.API_KEY, self.nodeId, scope, id, key)

    def get_aggData(
        self,
        variable_identifier: str,
        from_time: int,
        to_time: int,
        agg_interval_mins: int = 10,
    ) -> pd.DataFrame:
        return anedya_getAggData(
            variable_identifier,
            self.nodeId,
            from_time,
            to_time,
            self.API_KEY,
            agg_interval_mins,
        )


# ─────────────────────────────────────────────────────────────────────────────
# PAGINATED DATA FETCH — for report generation over long date ranges
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_chunk_raw(variable_identifier, nodeId, from_ep, to_ep, apiKey):
    """
    Fetches one chunk of raw data. Returns a list of {timestamp, value} dicts.
    No caching — used only during report generation.
    """
    url = "https://api.anedya.io/v1/data/getData"
    payload = json.dumps({
        "variable": variable_identifier,
        "nodes": [nodeId],
        "from": from_ep,
        "to": to_ep,
        "order": "asc",
    })
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {apiKey}",
    }
    try:
        response = st.session_state.http_client.request(
            "POST", url, headers=headers, data=payload, timeout=15
        )
        if not response.text.strip():
            return []
        if response.status_code == 200:
            data = json.loads(response.text).get("data", {})
            return data.get(nodeId, [])
        return []
    except Exception:
        return []


def get_data_paginated(
    variable_identifier: str,
    nodeId: str,
    from_time: int,
    to_time: int,
    apiKey: str,
    chunk_days: int = 1,
) -> pd.DataFrame:
    """
    Splits [from_time, to_time] into chunk_days-sized windows and fetches each
    separately, then merges into one DataFrame. Handles deduplication.
    """
    CHUNK_SECS = chunk_days * 86400
    DELAY = 0.25  # seconds between requests

    all_points = []
    cur = from_time
    while cur < to_time:
        nxt = min(cur + CHUNK_SECS - 1, to_time)
        pts = _fetch_chunk_raw(variable_identifier, nodeId, cur, nxt, apiKey)
        all_points.extend(pts)
        cur += CHUNK_SECS
        time.sleep(DELAY)

    if not all_points:
        return pd.DataFrame()

    # Deduplicate
    seen = set()
    unique = []
    for p in all_points:
        ts = p.get("timestamp")
        if ts not in seen:
            seen.add(ts)
            unique.append(p)

    df = pd.DataFrame(unique).sort_values("timestamp").reset_index(drop=True)
    df["Datetime"] = pd.to_datetime(df["timestamp"], unit="s")
    local_tz = pytz.timezone("Asia/Kolkata")
    df["Datetime"] = df["Datetime"].dt.tz_localize("UTC").dt.tz_convert(local_tz)
    df.set_index("Datetime", inplace=True)
    df.drop(columns=["timestamp"], inplace=True)
    return df.reset_index()


# ─────────────────────────────────────────────────────────────────────────────
# EXISTING FUNCTIONS — unchanged
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=40, show_spinner=False)
def anedya_getDeviceStatus(apiKey, nodeId) -> dict:
    url = "https://api.anedya.io/v1/health/status"
    apiKey_in_formate = "Bearer " + apiKey

    payload = json.dumps({"nodes": [nodeId], "lastContactThreshold": 900})
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": apiKey_in_formate,
    }

    response = st.session_state.http_client.request(
        "POST", url, headers=headers, data=payload, timeout=10
    )
    responseMessage = response.text

    errorCode = json.loads(responseMessage).get("errcode")
    if errorCode == 0:
        device_status = (
            json.loads(responseMessage).get("data")[nodeId].get("online")
        )
        value = {"isSuccess": True, "device_status": device_status}
    else:
        print(responseMessage)
        value = {"isSuccess": False, "device_status": None}

    return value


@st.cache_data(ttl=5, show_spinner=False)
def get_latestData(
    param_variable_identifier: str, nodeId: str, apiKey: str
) -> dict:

    url = "https://api.anedya.io/v1/data/latest"
    apiKey_in_formate = "Bearer " + apiKey

    payload = json.dumps(
        {"nodes": [nodeId], "variable": param_variable_identifier}
    )
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": apiKey_in_formate,
    }

    response = st.session_state.http_client.request(
        "POST", url, headers=headers, data=payload, timeout=10
    )
    response_message = response.text
    if response.status_code == 200:
        data = json.loads(response_message).get("data")
        if data == {} or data is None:
            return {"isSuccess": False, "data": None, "timestamp": None}
        else:
            data = data[nodeId].get("value")
            timestamp = (
                json.loads(response_message).get("data")[nodeId].get("timestamp")
            )
            return {"isSuccess": True, "data": data, "timestamp": timestamp}
    else:
        st.error("Get LatestData API failed")
        return {"isSuccess": False, "data": None, "timestamp": None}


@st.cache_data(ttl=30, show_spinner=False)
def get_data(
    variable_identifier: str,
    nodeId: str,
    from_time: int,
    to_time: int,
    apiKey: str,
) -> pd.DataFrame:

    url = "https://api.anedya.io/v1/data/getData"
    apiKey_in_formate = "Bearer " + apiKey

    payload = json.dumps(
        {
            "variable": variable_identifier,
            "nodes": [nodeId],
            "from": from_time,
            "to": to_time,
            "limit": 10000,
            "order": "desc",
        }
    )
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": apiKey_in_formate,
    }

    response = st.session_state.http_client.request(
        "POST", url, headers=headers, data=payload, timeout=10
    )
    response_message = response.text

    if response.status_code == 200:
        data_list = []
        response_data = json.loads(response_message).get("data")
        for timeStamp, value in response_data.items():
            for entry in value:
                data_list.append(entry)

        if data_list:
            df = pd.DataFrame(data_list)
            if df.duplicated(subset=["timestamp"]).any():
                df.drop_duplicates(subset=["timestamp"], keep="first", inplace=True)
            df["Datetime"] = pd.to_datetime(df["timestamp"], unit="s")
            local_tz = pytz.timezone("Asia/Kolkata")
            df["Datetime"] = (
                df["Datetime"].dt.tz_localize("UTC").dt.tz_convert(local_tz)
            )
            df.set_index("Datetime", inplace=True)
            df.drop(columns=["timestamp"], inplace=True)
            chart_data = df.reset_index()
        else:
            chart_data = pd.DataFrame()
        return chart_data
    else:
        print(response_message[0])
        return pd.DataFrame()


@st.cache_data(ttl=30, show_spinner=False)
def anedya_getAggData(
    variable_identifier: str,
    nodeId: str,
    from_time: int,
    to_time: int,
    apiKey: str,
    agg_interval_mins: int,
) -> pd.DataFrame:
    url = "https://api.anedya.io/v1/aggregates/variable/byTime"
    apiKey_in_formate = "Bearer " + apiKey

    payload = json.dumps(
        {
            "variable": variable_identifier,
            "from": from_time,
            "to": to_time,
            "config": {
                "aggregation": {"compute": "avg", "forEachNode": True},
                "interval": {
                    "measure": "minute",
                    "interval": agg_interval_mins,
                },
                "responseOptions": {"timezone": "UTC"},
                "filter": {"nodes": [nodeId], "type": "include"},
            },
        }
    )
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": apiKey_in_formate,
    }

    response = st.session_state.http_client.request(
        "POST", url, headers=headers, data=payload
    )
    response_message = response.text

    if response.status_code == 200:
        data_list = []
        response_data = json.loads(response_message).get("data")
        for timeStamp, aggregate in response_data.items():
            for entry in aggregate:
                data_list.append(entry)

        if data_list:
            df = pd.DataFrame(data_list)
            if df.duplicated(subset=["timestamp"]).any():
                df.drop_duplicates(subset=["timestamp"], keep="first", inplace=True)
            df["Datetime"] = pd.to_datetime(df["timestamp"], unit="s")
            local_tz = pytz.timezone("Asia/Kolkata")
            df["Datetime"] = (
                df["Datetime"].dt.tz_localize("UTC").dt.tz_convert(local_tz)
            )
            df.set_index("Datetime", inplace=True)
            df.drop(columns=["timestamp"], inplace=True)
            chart_data = df.reset_index()
        else:
            chart_data = pd.DataFrame()
        return chart_data
    else:
        print(response_message[0])
        return pd.DataFrame()


@st.cache_data(ttl=1, show_spinner=False)
def anedya_getValueStore(
    apiKey,
    nodeId,
    scope: str = "node",
    id: str = "",
    key: str = "",
) -> dict:
    url = "https://api.anedya.io/v1/valuestore/getValue"

    if scope != "global":
        id = nodeId

    payload = json.dumps(
        {"namespace": {"scope": scope, "id": id}, "key": key}
    )
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {apiKey}",
    }

    response = st.session_state.http_client.request(
        "POST", url, headers=headers, data=payload
    )
    responseMessage = response.text

    isSucess = json.loads(responseMessage).get("success")
    if isSucess:
        value = json.loads(responseMessage).get("value")
        value = {"isSuccess": True, "key": key, "value": value}
    else:
        print(responseMessage)
        value = {"isSuccess": False, "key": key, "value": None}

    return value
