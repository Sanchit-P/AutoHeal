import aiosqlite

DB_PATH = "autoheal.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS healing_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                metric_snapshot TEXT,
                anomaly_type TEXT,
                healing_action TEXT,
                confidence REAL,
                dry_run INTEGER
            )
        """)
        await db.commit()

async def insert_log(entry: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO healing_log 
            (timestamp, metric_snapshot, anomaly_type, healing_action, confidence, dry_run)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            entry["timestamp"], entry["metric_snapshot"],
            entry["anomaly_type"], entry["healing_action"],
            entry["confidence"], entry["dry_run"]
        ))
        await db.commit()

async def get_logs(limit=20):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM healing_log ORDER BY id DESC LIMIT ?", (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return rows