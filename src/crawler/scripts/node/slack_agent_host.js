const { App } = require('@slack/bolt');
const { exec } = require('node:child_process');
const path = require('node:path');
require('dotenv').config({ path: path.join(__dirname, '../../..', '.env') });

const botToken = process.env.SLACK_BOT_TOKEN;
const appToken = process.env.SLACK_APP_TOKEN;
const conversationId = process.env.ANTIGRAVITY_CONVERSATION_ID || '215f3ff7-4e20-476d-9fe3-b57b3c74f132';

if (!botToken || !appToken) {
  console.error('Error: SLACK_BOT_TOKEN and SLACK_APP_TOKEN must be set in .env');
  process.exit(1);
}

const app = new App({
  token: botToken,
  appToken: appToken,
  socketMode: true
});

const fs = require('node:fs');

const defaultWinAgy = String.raw`C:\Users\weare\AppData\Local\agy\bin\agy.exe`;
const agyPath = process.env.AGY_PATH || (fs.existsSync(defaultWinAgy) ? defaultWinAgy : 'agy');

const rawAllowedUsers = process.env.SLACK_ALLOWED_USERS || '';
const allowedUsers = new Set(rawAllowedUsers.split(',').map(s => s.trim()).filter(Boolean));

const rawAllowedBots = process.env.SLACK_ALLOWED_BOT_IDS || '';
const allowedBots = new Set(rawAllowedBots.split(',').map(s => s.trim()).filter(Boolean));

const AUTO_HEAL_TAG = '[AUTO_HEAL_REQ]';
const SELF_AGENT_MARKERS = [
  'Antigravity Agent 本体を起動中',
  'Antigravity Agent 実行完了',
  'Antigravity Agent タスク完了',
  'Antigravity Agent 実行中'
];

function isSelfAgentMessage(text) {
  return SELF_AGENT_MARKERS.some(marker => text.includes(marker));
}

function shouldProcessEvent(event) {
  const text = (event.text || '').trim();
  if (!text) return { valid: false, instruction: '' };
  if (isSelfAgentMessage(text)) return { valid: false, instruction: '' };

  const botId = event.bot_id;
  const userId = event.user;

  if (text.includes(AUTO_HEAL_TAG)) {
    if (botId) {
      if (allowedBots.size === 0 || !allowedBots.has(botId)) {
        return { valid: false, instruction: '', reason: 'unauthorized_bot' };
      }
      return { valid: true, instruction: '/auto-heal', isAutoHeal: true };
    }
    if (userId) {
      if (allowedUsers.size === 0 || !allowedUsers.has(userId)) {
        return { valid: false, instruction: '', reason: 'unauthorized_user' };
      }
      return { valid: true, instruction: '/auto-heal', isAutoHeal: true };
    }
    return { valid: false, instruction: '', reason: 'unauthorized_sender' };
  }

  if (botId) {
    return { valid: false, instruction: '' };
  }

  if (!userId || allowedUsers.size === 0 || !allowedUsers.has(userId)) {
    return { valid: false, instruction: '', reason: 'unauthorized_user' };
  }

  return { valid: true, instruction: text, isAutoHeal: false };
}

/**
 * Start the configured agent command for a Slack message and post its result.
 *
 * Userless, empty, and bot events are ignored unless they match the auto-heal request.
 * The returned promise resolves after the command starts, before its completion reply is posted.
 *
 * @param {Function} say Slack Bolt function used to post thread replies.
 * @param {object} event Slack message event containing text and thread metadata.
 * @returns {Promise<void>}
 */
async function processInstruction(say, event) {
  const { valid, instruction } = shouldProcessEvent(event);
  if (!valid) {
    return;
  }

  const userId = event.user || 'SystemBot';
  const threadTs = event.thread_ts || event.ts;

  console.log(`[SlackAgent] Received instruction from ${userId}: ${instruction}`);

  await say({
    text: `🚀 **Antigravity Agent 本体を起動中...** タスクを実行します。`,
    thread_ts: threadTs
  });

  const escapedText = instruction.replaceAll('"', String.raw`\"`);
  const cmd = `"${agyPath}" --dangerously-skip-permissions --conversation "${conversationId}" -p "${escapedText}"`;
  console.log(`[SlackAgent] Running CLI: ${cmd}`);

  const env = { ...process.env, PAGER: 'cat' };

  // nosemgrep: javascript.lang.security.detect-child-process.detect-child-process
  exec(cmd, { cwd: path.join(__dirname, '../../..'), env, maxBuffer: 10 * 1024 * 1024, timeout: 600000 }, async (error, stdout, stderr) => {
    let output = (stdout || stderr || '').trim();
    const success = !error;
    const statusEmoji = success ? '✅' : '⚠️';

    if (!output) {
      output = error ? `Execution failed: ${error.message}` : '(Antigravity Agent からの出力はありませんでした。)';
    }

    const outputShort = output.length > 3500 ? output.slice(-3500) : output;

    await say({
      text: `${statusEmoji} **Antigravity Agent 実行完了**\n\n\`\`\`\n${outputShort}\n\`\`\``,
      thread_ts: threadTs
    });
  });
}

app.event('app_mention', async ({ event, say }) => {
  await processInstruction(say, event);
});

app.event('message', async ({ event, say }) => {
  if (!event.subtype) {
    await processInstruction(say, event);
  }
});

(async () => {
  try {
    await app.start();
    console.log('⚡️ Antigravity-integrated Slack Agent Socket Mode Connected Successfully!');
  } catch (err) {
    console.error('Failed to start Slack Agent Socket Mode:', err);
  }
})();
