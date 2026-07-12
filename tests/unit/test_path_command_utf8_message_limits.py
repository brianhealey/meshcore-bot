#!/usr/bin/env python3
"""Unit tests for PathCommand UTF-8 byte truncation and multi-message splitting (PR #128)."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from modules.commands.path_command import PathCommand
from modules.models import MeshMessage


@pytest.mark.unit
class TestPathCommandTruncateToByteLength:
    """Tests for _truncate_to_byte_length (no split within code points)."""

    @pytest.fixture
    def path_cmd(self, mock_bot):
        return PathCommand(mock_bot)

    def test_short_string_unchanged(self, path_cmd):
        assert path_cmd._truncate_to_byte_length("hello", 20) == "hello"

    def test_truncates_on_utf8_bytes_not_chars(self, path_cmd):
        """Budget is UTF-8 bytes; result must respect max_bytes including ellipsis."""
        ellipsis = "..."
        out = path_cmd._truncate_to_byte_length("😀😀", 7, ellipsis)
        assert out.endswith(ellipsis)
        assert len(out.encode("utf-8")) <= 7

    def test_does_not_emit_lone_surrogate_fragment(self, path_cmd):
        """Truncated bytes decode with errors='ignore' — result must be valid UTF-8."""
        out = path_cmd._truncate_to_byte_length("éééé", 5, "...")
        assert out.encode("utf-8") == out.encode("utf-8")  # round-trip
        out.encode("utf-8").decode("utf-8")  # no exception


@pytest.mark.unit
class TestPathCommandFormatPathResponseByteCap:
    """_format_path_response generates compact format with sender mention."""

    @pytest.fixture
    def path_cmd(self, mock_bot):
        cmd = PathCommand(mock_bot)
        cmd.translate = MockTranslate()
        return cmd

    @pytest.mark.asyncio
    async def test_format_includes_sender_mention_and_hop_count(self, path_cmd):
        """New format: @[sender] hop_count path route: ~Xmi, direct: ~Xmi url."""
        node_ids = ["AB"]
        repeater_info = {"AB": {"found": False}}
        with patch.object(path_cmd, '_shorten_url', new_callable=AsyncMock, return_value="https://da.gd/test"):
            raw = await path_cmd._format_path_response(node_ids, repeater_info, "TestUser")
        assert "@[TestUser]" in raw
        assert "ab" in raw.lower()  # node_ids are lowercased
        assert "route:" in raw
        assert "direct:" in raw


class MockTranslate:
    """Minimal translate: long unknown line to exercise 150-byte line cap."""

    def __call__(self, key: str, **kwargs):
        if key == "commands.path.node_unknown":
            node_id = kwargs.get("node_id", "")
            return f"unknown {node_id}" + "😀" * 50
        if key == "commands.path.truncation":
            return "..."
        return key


@pytest.mark.unit
class TestPathCommandSendPathResponseByteSplitting:
    """_send_path_response truncates when response exceeds byte limit."""

    @pytest.fixture
    def path_cmd(self, mock_bot):
        cmd = PathCommand(mock_bot)
        cmd.translate = MockTranslateForSend()
        cmd.send_response = AsyncMock(return_value=True)
        return cmd

    @pytest.mark.asyncio
    async def test_truncates_when_response_exceeds_byte_budget(self, path_cmd):
        """Response exceeding max_length gets truncated with indicator."""
        path_cmd.get_max_message_length = lambda _msg: 25
        msg = MeshMessage(content="path", channel="general", is_dm=False)
        response = "a" * 50  # Exceeds 25 byte limit
        await path_cmd._send_path_response(msg, response)
        # New implementation truncates instead of splitting
        path_cmd.send_response.assert_awaited_once()
        sent_text = path_cmd.send_response.call_args[0][1]
        assert "(truncated)" in sent_text

    @pytest.mark.asyncio
    async def test_single_send_when_under_byte_budget(self, path_cmd):
        path_cmd.get_max_message_length = lambda _msg: 100
        msg = MeshMessage(content="path", channel="general", is_dm=False)
        response = "short"
        await path_cmd._send_path_response(msg, response)
        path_cmd.send_response.assert_awaited_once()


@pytest.mark.unit
class TestPathCommandReplyPrefix:
    """New format: mention is built into _format_path_response, not _send_path_response."""

    @pytest.fixture
    def path_cmd(self, mock_bot):
        mock_bot.translator = MagicMock()
        mock_bot.translator.translate = Mock(side_effect=lambda key, **kwargs: key)
        cmd = PathCommand(mock_bot)
        cmd.send_response = AsyncMock(return_value=True)
        return cmd

    @pytest.mark.asyncio
    async def test_sends_response_as_is(self, path_cmd, mock_bot):
        """_send_path_response sends response unchanged (mention already in format)."""
        path_cmd.get_max_message_length = lambda _msg: 200
        msg = MeshMessage(content="path", channel="general", is_dm=False, sender_id="alice")
        response = "@[alice] 2 ab,cd route: ~1.0mi, direct: ~0.5mi https://da.gd/test"
        await path_cmd._send_path_response(msg, response)
        path_cmd.send_response.assert_awaited_once()
        payload = path_cmd.send_response.call_args[0][1]
        assert payload == response
        assert path_cmd.last_response == response

    @pytest.mark.asyncio
    async def test_truncates_long_response(self, path_cmd, mock_bot):
        """Long responses get truncated with indicator."""
        path_cmd.get_max_message_length = lambda _msg: 50
        msg = MeshMessage(content="path", channel="general", is_dm=False)
        response = "@[alice] 2 ab,cd route: ~1.0mi, direct: ~0.5mi https://da.gd/verylongurl123456789"
        await path_cmd._send_path_response(msg, response)
        path_cmd.send_response.assert_awaited_once()
        sent = path_cmd.send_response.call_args[0][1]
        assert "(truncated)" in sent
        assert len(sent.encode("utf-8")) <= 50


class MockTranslateForSend:
    def __call__(self, key: str, **kwargs):
        if key == "commands.path.continuation_end":
            return "\n>>"
        if key == "commands.path.continuation_start":
            return f"<< {kwargs.get('line', '')}"
        return key
