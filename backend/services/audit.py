from sqlmodel import Session

from database import engine


def add_audit_log(
    user_id: str,
    username: str,
    action: str,
    target: str = None,
    detail: str = None,
    session: Session = None,
):
    """
    记录审计日志。
    如果传入 session，则使用该 session；否则创建新 session。
    """
    from models.audit_log import AuditLog

    log = AuditLog(
        user_id=user_id,
        username=username,
        action=action,
        target=target,
        detail=detail,
    )

    if session:
        session.add(log)
        session.commit()
    else:
        with Session(engine) as sess:
            sess.add(log)
            sess.commit()
