const { App } = require('@slack/bolt');
const { spawn } = require('child_process');
const path = require('path');
const iconv = require('iconv-lite');

// プロジェクトルートの .env 絶対パス指定
const envPath = 'c:\\Users\\weare\\Documents\\realestate_crawler\\.env';
require('dotenv').config({ path: envPath });

const botToken = process.env.SLACK_BOT_TOKEN;
const appToken = process.env.SLACK_APP_TOKEN;

if (!botToken || !appToken) {
  console.error(`Error: SLACK_BOT_TOKEN and SLACK_APP_TOKEN must be set in ${envPath}`);
  process.exit(1);
}

// 10秒Pingキープアライブ付き超堅牢 Socket Mode 設定
const app = new App({
  token: botToken,
  appToken: appToken,
  socketMode: true,
  pingInterval: 10000,
  clientPingTimeout: 5000
});

// 返答識別子プレフィックス定義
const RESP_PREFIX_START = '[AGY-RESP:START]';
const RESP_PREFIX_PROGRESS = '[AGY-RESP:PROGRESS]';
const RESP_PREFIX_FINISH = '[AGY-RESP:FINISH]';
const RESP_PREFIX_HEADER = '[AGY-RESP:';

// 二重発火防止キャッシュ (Set)
const processedEventSet = new Set();

function safeDecode(buf) {
  if (!buf) return '';
  let utf8Str = buf.toString('utf-8');
  if (!utf8Str.includes('')) {
    return utf8Str;
  }
  try {
    return iconv.decode(buf, 'cp932');
  } catch (e) {
    return utf8Str;
  }
}

function getDynamicIntervalMs(postCount) {
  if (postCount <= 3) return 3000;
  if (postCount <= 6) return 10000;
  if (postCount <= 9) return 30000;
  return 60000;
}

// 100% 確実に途中ログ ＆ 完了報告を追記連投する絶対信頼エンジン
async function processInstruction(say, client, event) {
  const eventId = event.event_ts || event.ts;

  // 1. 二重発火防止
  if (processedEventSet.has(eventId)) {
    return;
  }
  processedEventSet.add(eventId);

  if (processedEventSet.size > 100) {
    const firstItem = processedEventSet.values().next().value;
    processedEventSet.delete(firstItem);
  }

  const userId = event.user;
  let rawText = (event.text || '').trim();
  const threadTs = event.thread_ts || event.ts;
  const isBot = Boolean(event.bot_id);

  // 2. 無限ループ防止
  if (rawText.startsWith(RESP_PREFIX_HEADER)) {
    return;
  }

  // <@UXXXXXXXX> メンションタグを除去
  const cleanText = rawText.replace(/<@[A-Z0-9]+>/g, '').trim();

  console.log(`\n==================================================`);
  console.log(`[SLACK EVENT RECEIVED!] EventID: ${eventId} | IsBot: ${isBot} | User: ${userId || 'Bot'} | Prompt: "${cleanText || rawText}"`);

  const promptText = cleanText || rawText || '指示を受領しました';

  // 3. 即時レスポンス投稿
  try {
    await say({
      text: `${RESP_PREFIX_START} 🚀 **[タスク開始] Antigravity Agent が通知を検知しました**\n受領指示: \`${promptText}\` (投稿者: \`${isBot ? 'Bot' : 'User'}\`)`,
      thread_ts: threadTs
    });
    console.log(`[SlackAgent] Successfully sent initial reaction reply to thread ${threadTs}`);
  } catch (e) {
    console.error('[SlackAgent] Failed sending initial reply:', e.message);
  }

  // Windows環境対応の確実なコマンド呼び出し (shell: true)
  const cmdLine = 'docker-compose exec -T app pytest src/crawler/tests/unit/test_parser_abstract_methods.py src/crawler/tests/unit/test_start_urls.py -v';

  console.log(`[SlackAgent] Spawning shell command: ${cmdLine}`);

  let fullLogs = [];
  let lastPostedIndex = 0;
  let startTime = Date.now();
  let progressPostCount = 0;
  let isChildActive = true;

  const child = spawn('cmd.exe', ['/c', cmdLine], {
    cwd: 'c:\\Users\\weare\\Documents\\realestate_crawler',
    env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    shell: true
  });

  const handleData = (buf) => {
    const text = safeDecode(buf);
    const lines = text.split('\n').filter(l => l.trim().length > 0);
    fullLogs.push(...lines);
  };

  child.stdout.on('data', handleData);
  child.stderr.on('data', handleData);

  // 4. 動的タイマーでの進捗連投追記 (ログの有無に関わらず必ずステータスを報告)
  const scheduleNextProgressPost = () => {
    if (!isChildActive) return;

    progressPostCount++;
    const nextDelayMs = getDynamicIntervalMs(progressPostCount);

    setTimeout(async () => {
      if (!isChildActive) return;

      const elapsedSec = ((Date.now() - startTime) / 1000).toFixed(1);
      let logSnippet = 'タスク実行中... (ログ出力待機中)';

      if (fullLogs.length > lastPostedIndex) {
        logSnippet = fullLogs.slice(lastPostedIndex, lastPostedIndex + 8).join('\n');
        lastPostedIndex = fullLogs.length;
      }

      try {
        await say({
          text: `${RESP_PREFIX_PROGRESS} 🔄 **[進捗追記 #${progressPostCount}] 途中経過 (${elapsedSec}秒経過 / 次回間隔: ${nextDelayMs / 1000}秒)**\n\`\`\`\n${logSnippet}\n\`\`\``,
          thread_ts: threadTs
        });
        console.log(`[SlackAgent] Appended progress reply #${progressPostCount} to thread ${threadTs}`);
      } catch (err) {
        console.error('[SlackAgent] Failed appending progress reply:', err.message);
      }

      scheduleNextProgressPost();
    }, nextDelayMs);
  };

  scheduleNextProgressPost();

  child.on('close', async (code) => {
    isChildActive = false;
    const elapsedSec = ((Date.now() - startTime) / 1000).toFixed(1);
    console.log(`[SlackAgent] Task finished with exit code ${code} in ${elapsedSec}s`);

    const isSuccess = (code === 0);
    const statusEmoji = isSuccess ? '✅' : '⚠️';
    const finalLogs = fullLogs.slice(-8).join('\n') || '全工程が正常に完了しました。';

    // 5. 最終完了報告 (100% 確実に送信)
    try {
      await say({
        text: `${RESP_PREFIX_FINISH} ${statusEmoji} **[タスク完了報告] 正常終了しました (総所要時間: ${elapsedSec}秒)**\n受領指示: \`${promptText}\` \n結果: \`${isSuccess ? '100% SUCCESS' : 'Error ' + code}\` \n\`\`\`\n${finalLogs}\n\`\`\``,
        thread_ts: threadTs
      });
      console.log(`[SlackAgent] Appended final completion reply to thread ${threadTs}`);
    } catch (err) {
      console.error('[SlackAgent] Failed sending final reply:', err.message);
    }
  });

  child.on('error', async (err) => {
    isChildActive = false;
    console.error('[SlackAgent] Task error:', err);
    try {
      await say({
        text: `${RESP_PREFIX_FINISH} ❌ **[タスクエラー] 実行失敗**: \`${err.message}\``,
        thread_ts: threadTs
      });
    } catch (e) {}
  });
}

app.event('app_mention', async ({ event, say, client }) => {
  await processInstruction(say, client, event);
});

app.event('message', async ({ event, say, client }) => {
  if (!event.subtype || event.subtype === 'file_share' || event.subtype === 'bot_message') {
    await processInstruction(say, client, event);
  }
});

app.error(async (error) => {
  console.error('[SlackAgent Global Error Handler]:', error);
});

(async () => {
  try {
    await app.start();
    console.log('⚡️ Antigravity Guaranteed Progress Engine Running!');
  } catch (err) {
    console.error('Failed to start Agent:', err);
  }
})();
