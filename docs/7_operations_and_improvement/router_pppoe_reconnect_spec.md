# ルーターPPPoE動的IP再取得・ポリシールーティング運用仕様書

## 1. 概要
健美家等の厳格なWAF・データセンターIP拒否を実施している不動産ポータルに対して、ローカル環境のトラベルルーター（GL.iNet GL-MT3000）のWAN_PPPOEインターフェースを切断・再接続し、動的家庭用IPを再取得した上でクローリングを実行する事前処理機構の仕様を定義する。

## 2. アーキテクチャとルーティング構成
```
[Local PC (Windows)]
      │
      ▼
[GL.iNet GL-MT3000 (OpenWrt 21.02)]
   ├── デフォルトルーティング: ds-xpass (クロスパス Dual-Stack Lite)
   └── ポリシールーティング: vpn-policy-routing (VPR)
         └── ルール: kenbiya_pppoe (dest_addr: kenbiya.com, www.kenbiya.com, AWS ELB IP群)
               └── 出口: pppoe-wan_pppoe (WAN_PPPOE インターフェース)
```

## 3. 自動再取得プロトコル (`router_controller.py`)
1. **環境検証**:
   - `GL_ROUTER_PASSWORD` 未設定時、または `IS_CLOUD`（Cloud Run等のクラウド実行環境）検知時は安全にスキップ（クラウドパイプラインへの副作用ゼロ）。
2. **LuCI セッション確立**:
   - ヘッドレスブラウザ（Playwright）を用いてローカルルーターのLuCI Web管理画面（ポート8080）へ認証接続。
3. **PPPoE切断・再接続**:
   - `/sbin/ifdown wan_pppoe` を LuCI API 経由で実行。
   - 15秒間待機（ISP側での完全セッション切断を担保）。
   - `/sbin/ifup wan_pppoe` を実行。
   - 最大30秒間ポーリングし、新しいグローバルIPアドレスの割り当てを確認。
4. **VPRサービス再適用**:
   - ルーティングテーブル・ポリシールールの一貫性を保証するため `/etc/init.d/vpn-policy-routing restart` を実行。

## 4. 実行トリガー (`run_all_crawlers.py`)
- クローラー全件実行スクリプトの起動時事前処理（`clean_zombies()` 直後）に `ensure_router_pppoe_reconnected()` を呼び出し、IP再取得を実施。
- 再取得失敗時も例外でメインプロセスを落とさず、警告ログを出力して通常クローリングへフォールバックする耐障害性設計を採用。
- クローラー全件実行スクリプトの終了処理（`finally` ブロック等）にて `ensure_router_pppoe_disconnected()` を呼び出し、`wan_pppoe` を切断（`/sbin/ifdown wan_pppoe`）する。未使用時のセッション維持を避け、次回起動時の別IP割り当てを促進する。
