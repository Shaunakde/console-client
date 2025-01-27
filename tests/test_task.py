#!/usr/bin/env python

import pytest

from capella_console_client.config import CONSOLE_API_URL
from capella_console_client import CapellaConsoleClient
from capella_console_client.exceptions import TaskNotCompleteError
from .test_data import get_mock_responses


def test_list_all_tasking_requests(test_client, authed_tasking_request_mock):
    tasking_requests = test_client.list_tasking_requests()
    assert tasking_requests == get_mock_responses("/tasks?customerId=MOCK_ID")


def test_list_all_tasking_requests_for_org(test_client, authed_tasking_request_mock):
    tasking_requests = test_client.list_tasking_requests(for_org=True)
    assert tasking_requests == get_mock_responses("/tasks?organizationId=MOCK_ORG_ID")


def test_list_tasking_with_id_single(test_client, authed_tasking_request_mock, disable_validate_uuid):
    tasking_requests = test_client.list_tasking_requests("abc")
    assert len(tasking_requests) == 1
    assert tasking_requests[0]["properties"]["taskingrequestId"] == "abc"


def test_list_tasking_with_id_multiple(test_client, authed_tasking_request_mock, disable_validate_uuid):
    tasking_requests = test_client.list_tasking_requests("abc", "def")
    assert len(tasking_requests) == 2

    found_ids = [t["properties"]["taskingrequestId"] for t in tasking_requests]
    assert "abc" in found_ids
    assert "def" in found_ids


def test_list_tasking_with_id_single_status(test_client, authed_tasking_request_mock, disable_validate_uuid):
    tasking_requests = test_client.list_tasking_requests(status="completed")
    assert len(tasking_requests) == 1
    assert tasking_requests[0]["properties"]["taskingrequestId"] == "abc"


def test_list_tasking_with_id_single_status_case_insensitive(
    test_client, authed_tasking_request_mock, disable_validate_uuid
):
    tasking_requests = test_client.list_tasking_requests(status="cOmPlEtEd")
    assert len(tasking_requests) == 1
    assert tasking_requests[0]["properties"]["taskingrequestId"] == "abc"


def test_list_tasking_with_id_single_status_with_ids(test_client, authed_tasking_request_mock, disable_validate_uuid):
    tasking_requests = test_client.list_tasking_requests("abc", "def", status="completed")
    assert len(tasking_requests) == 1
    assert tasking_requests[0]["properties"]["taskingrequestId"] == "abc"


def test_list_tasking_with_id_single_status_nonexistent(
    test_client, authed_tasking_request_mock, disable_validate_uuid
):
    tasking_requests = test_client.list_tasking_requests("abc", "def", status="doesnotexist-status")
    assert tasking_requests == []


def test_get_task(test_client, authed_tasking_request_mock):
    task = test_client.get_task("abc")

    assert task == get_mock_responses("/task/abc")
    assert task["properties"]["taskingrequestId"] == "abc"


def test_task_is_completed(authed_tasking_request_mock):
    client = CapellaConsoleClient(email="MOCK_EMAIL", password="MOCK_PW")
    task = client.get_task("abc")

    assert client.is_task_completed(task)


def test_get_collects_for_task(test_client, authed_tasking_request_mock):
    authed_tasking_request_mock.add_response(
        url=f"{CONSOLE_API_URL}/collects/list/abc",
        json=get_mock_responses("/collects/list/abc"),
    )

    collects = test_client.get_collects_for_task("abc")

    assert collects == get_mock_responses("/collects/list/abc")


def test_get_collects_for_task_not_completed(test_client, auth_httpx_mock):
    auth_httpx_mock.add_response(
        url=f"{CONSOLE_API_URL}/task/def",
        json=get_mock_responses("/task/def"),
    )

    # we should get task 'def', see that it's not completed, and throw an exception
    with pytest.raises(TaskNotCompleteError):
        test_client.get_collects_for_task("def")
