# ランブック: Docker デーモン制御およびヘッドレス運用手順

## 1. 概要
本ランブックは、ローカル環境において GUI 画面（Docker Desktop.exe）をポップアップさせず、ヘッドレス（サービス/デーモン）として Docker ランタイムを自律的に起動・制御するための具象手順を定義します。

---

## 2. Docker 状態確認手順

### 2.1. 疎通確認 (CLI)
```powershell
docker ps
```
- **判定**: コンテナ一覧が表示されれば正常稼働。
- **エラー時**: `open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.` 等のパイプ未接続エラーが返る。

---

## 3. ヘッドレス・デーモン起動手順

### 3.1. Windows ヘッドレス起動 (推奨)
GUI ウィンドウを表示させずにバックグラウンドでデーモンを起動します：
```powershell
Start-Process -FilePath "C:\Program Files\Docker\Docker\Docker Desktop.exe" -ArgumentList "--unattended" -WindowStyle Hidden
```

### 3.2. 起動完了の待機・検証 (Polling)
デーモンの立ち上がりまで数秒を要するため、以下のループまたはタイマーで疎通を確認します：
```powershell
$timeout = 30
$elapsed = 0
while ($elapsed -lt $timeout) {
    if (docker ps 2>$null) {
        Write-Output "Docker daemon is ready."
        break
    }
    Start-Sleep -Seconds 3
    $elapsed += 3
}
```

---

## 4. コンテナ起動・運用手順

### 4.1. バックグラウンド起動
```powershell
docker compose up -d
```

### 4.2. アプリコンテナ内コマンド実行
ホスト側の Python ではなく、必ずコンテナ内で実行します：
```powershell
docker compose exec -T app python --version
docker compose exec -T app pytest src/crawler/tests/unit/
```

### 4.3. 停止手順
```powershell
docker compose down
```
