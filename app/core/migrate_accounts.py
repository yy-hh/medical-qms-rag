"""账号体系的一次性/幂等迁移，启动时调用。

1. 建属主账号（梁洋洋）。
2. 把存量 generated_docs / notes 中 account_id 为空的行归到属主。
3. 把根目录旧的 company_profile.json 拷到属主账号目录（存在性守护，不覆盖）。

全部幂等，重启安全。
"""
import shutil
import logging
from pathlib import Path

from app.core import account_store, doc_store, note_store
from app.core.account_store import DEFAULT_ACCOUNT, DEFAULT_ACCOUNT_NAME

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LEGACY_PROFILE = BASE_DIR / "data" / "company_profile.json"
ACCOUNTS_DIR = BASE_DIR / "data" / "accounts"


def run_migration():
    # 1. 属主账号
    account_store.upsert_account(DEFAULT_ACCOUNT, DEFAULT_ACCOUNT_NAME)

    # 2. 回填存量文档/笔记的 account_id（触发 _db() 建表+补列）
    ddb = doc_store._db()
    with doc_store._lock:
        cur = ddb.execute(
            "UPDATE generated_docs SET account_id=? WHERE account_id='' OR account_id IS NULL",
            (DEFAULT_ACCOUNT,),
        )
        ddb.commit()
    if cur.rowcount:
        logger.info("迁移：%d 篇存量文档归属到属主账号", cur.rowcount)

    ndb = note_store._db()
    with note_store._lock:
        cur = ndb.execute(
            "UPDATE notes SET account_id=? WHERE account_id='' OR account_id IS NULL",
            (DEFAULT_ACCOUNT,),
        )
        ndb.commit()
    if cur.rowcount:
        logger.info("迁移：%d 条存量笔记归属到属主账号", cur.rowcount)

    # 3. 旧公司档案 → 属主账号目录（存在性守护）
    dest = ACCOUNTS_DIR / DEFAULT_ACCOUNT / "company_profile.json"
    if LEGACY_PROFILE.exists() and not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(LEGACY_PROFILE, dest)
        logger.info("迁移：旧公司档案已拷贝到属主账号目录 %s", dest)
