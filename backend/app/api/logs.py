import json

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse

from app.api.audit import get_audit_logs

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/export")
async def export_logs(format: str = Query(default="json")):
    logs = [log.model_dump(mode="json") for log in get_audit_logs()]
    if format == "csv":
        lines = ["id,created_at,final_verdict,final_reason,content"]
        for item in logs:
            row = [
                item["id"],
                item["created_at"],
                item["final_verdict"],
                item["final_reason"].replace(",", " "),
                item["content"].replace(",", " "),
            ]
            lines.append(",".join(row))
        return PlainTextResponse("\n".join(lines), media_type="text/csv")
    return PlainTextResponse(
        json.dumps(logs, ensure_ascii=False, indent=2), media_type="application/json"
    )

