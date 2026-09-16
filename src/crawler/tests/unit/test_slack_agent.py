# -*- coding: utf-8 -*-
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from package.utils.slack_agent import SlackAgent

def test_is_user_allowed():
    agent = SlackAgent(allowed_users=["U12345", "U67890"])
    assert agent.is_user_allowed("U12345") is True
    assert agent.is_user_allowed("U99999") is False

def test_is_user_allowed_empty_allowed():
    agent = SlackAgent(allowed_users=[])
    assert agent.is_user_allowed("ANY_USER") is True

@pytest.mark.asyncio
async def test_run_streaming_agent_mock():
    agent = SlackAgent(allowed_users=["U12345"], conversation_id="test-session-123")
    mock_client = MagicMock()
    mock_client.chat_update = MagicMock()
    
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.stdout.readline = AsyncMock(side_effect=[b"Processing instruction...\n", b"Done.\n", b""])
        mock_proc.wait = AsyncMock(return_value=0)
        mock_exec.return_value = mock_proc

        await agent.run_streaming_agent(mock_client, "C123", "123.456", "pytest実行して")
        assert mock_client.chat_update.called
