const { WebClient } = require('@slack/web-api');
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '../../..', '.env') });

const token = process.env.SLACK_BOT_TOKEN;
const channel = process.env.SLACK_DEV_CHANNEL || 'C0BKBHWD26T';

const client = new WebClient(token);

(async () => {
  try {
    console.log(`Sending test instruction to channel ${channel}...`);
    const result = await client.chat.postMessage({
      channel: channel,
      text: 'テスト投稿: pytest を実行して結果を報告してください。'
    });
    console.log('Successfully sent message:', result.ts);
  } catch (error) {
    console.error('Error sending message:', error);
  }
})();
