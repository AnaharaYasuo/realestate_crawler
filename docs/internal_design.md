# 内部設計書 (Internal Design)

本システムの内部構造、クラス継承関係、およびデータフローについて設計図を用いて説明します。

## 1. クラス継承図 (Class Diagram)

API通信およびクローリングの中核となるクラス群は、`ApiAsyncProcBase` を頂点とした継承構造を持っています。

```mermaid
classDiagram
    class ApiAsyncProcBase {
        <<Abstract>>
        -parser: ParserBase
        -semaphore: Semaphore
        +main(url)
        #_fetch()
        #_treatPage()*
        #_callApi()*
    }

    class ParseMiddlePageAsyncBase {
        <<Abstract>>
        #_treatPage()
        #_callApi()
        #_getParserFunc()*
    }

    class ParseDetailPageAsyncBase {
        <<Abstract>>
        #_run()
        #_treatPage()
        #_afterRunProc()
    }

    ApiAsyncProcBase <|-- ParseMiddlePageAsyncBase
    ApiAsyncProcBase <|-- ParseDetailPageAsyncBase

    ParseMiddlePageAsyncBase <|-- ParseMitsuiMansionArea
    ParseMiddlePageAsyncBase <|-- ParseMitsuiMansionList
    ParseDetailPageAsyncBase <|-- ParseMitsuiMansionDetail

    class ApiRegistry {
        -registry: dict
        +register(key, class)
        +get(key)
    }

    ApiAsyncProcBase ..> ApiRegistry : uses for local routing
```

---

## 2. API チェーン・データフロー (Sequence Diagram)

`task crawl` コマンド実行から DB 保存までのシーケンスです。

```mermaid
sequenceDiagram
    participant CLI as Task CLI
    participant Srv as API Server (main.py)
    participant Reg as ApiRegistry
    participant Proc as ApiAsyncProcBase
    participant Site as External Web Site
    participant DB as MySQL (Django ORM)

    CLI->>Srv: HTTP POST /api/.../start
    Srv->>Reg: get(path)
    Reg-->>Srv: Class Reference
    Srv->>Proc: main(url)
    
    loop API Chain (Start -> Region -> Area -> List)
        Proc->>Site: HTTP GET (HTML)
        Site-->>Proc: 200 OK
        Proc->>Proc: Parse URLs
        Proc->>Srv: HTTP POST /api/... (Async/Fire-and-Forget)
        Note right of Proc: or Local Routing directly
    end

    rect rgb(240, 240, 240)
    Note over Proc, DB: Detail Stage
    Proc->>Site: HTTP GET (Detail Page)
    Site-->>Proc: 200 OK
    Proc->>Proc: Extract Property Data
    Proc->>DB: item.save()
    end
    
    Proc-->>Srv: 200 finish
```

---

## 3. モデル継承関係 (Data Model Inheritance)

複数の物件種別やサイト間で共通するフィールドを効率的に管理するため、Django の抽象基底クラスを利用しています。

```mermaid
graph TD
    subgraph Django Models
        Base[django.db.models.Model]
        
        subgraph Sumifu
            SBase[SumifuModel<br/>Abstract Base: 69 fields]
            SM[SumifuMansion]
            SK[SumifuKodate]
            ST[SumifuTochi]
            SI[SumifuInvestment]
        end

        subgraph Misawa
            MBase[MisawaCommon<br/>Abstract Base: 21 fields]
            MM[MisawaMansion]
            MK[MisawaKodate]
            MT[MisawaTochi]
            MIN[MisawaInvestment]
        end

        Base --> SBase
        SBase --> SM
        SBase --> SK
        SBase --> ST
        Base --> SI

        Base --> MBase
        MBase --> MM
        MBase --> MK
        MBase --> MT
        MBase --> MIN
    end
```

---

## 4. 重複検知ロジック

本システムでは、物件の重複を `pageUrl` フィールドで識別します。
- **Index**: データベースレベルで `pageUrl` に UNIQUE インデックスまたは一般インデックスを付与。
- **Save Logic**: 既存のURLが見つかった場合、Django ORM の `update_or_create` 相当のロジック、または保存前の存在チェックにより、データの「新規作成」か「更新」かを判別します。
