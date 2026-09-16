const { App } = require('@slack/bolt');
const { exec } = require('child_process');
const path = require('path');
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

const agyPath = 'C:\\Users\\weare\\AppData\\Local\\agy\\bin\\agy.exe';

async function processInstruction(say, event) {
  const userId = event.user;
  const text = (event.text || '').trim();
  const threadTs = event.thread_ts || event.ts;

  // 無限ループ防止（ボット自身の発言は無視）
  if (!userId || event.bot_id || !text) {
    return;
  }

  console.log(`[SlackAgent] Received instruction from ${userId}: ${text}`);

  await say({
    text: `🚀 **Antigravity Agent 本体を起動中...** タスクを実行します。`,
    thread_ts: threadTs
  });

  const cmd = `"${agyPath}" --dangerously-skip-permissions --conversation "${conversationId}" -p "${text.replace(/"/g, '\\"')}"`;
  console.log(`[SlackAgent] Running CLI: ${cmd}`);

  const env = { ...process.env, PAGER: 'cat' };

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
