def paginate_query(query, page: int, page_size: int):
    total = query.count()
    page = 1 if page < 1 else page
    page_size = 1 if page_size < 1 else page_size
    try:
        items = query.offset((page - 1) * page_size).limit(page_size).all()
    except Exception:
        all_items = query.all()
        start = (page - 1) * page_size
        end = start + page_size
        items = all_items[start:end]
    return items, total
from sqlalchemy import select, func

def _is_dm_session(session) -> bool:
    try:
        url = str(session.bind.url).lower()  # type: ignore
        return url.startswith("dm://") or "dm" in url
    except Exception:
        return False

def paginate_ids_with_row_number(session, base_query, pk_column, order_column, desc: bool, page: int, page_size: int):
    total = base_query.count()
    page = 1 if page < 1 else page
    page_size = 1 if page_size < 1 else page_size

    if not _is_dm_session(session):
        items = base_query.order_by(order_column.desc() if desc else order_column.asc()) \
            .offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    subq = base_query.order_by(None).statement.subquery("q")
    pk_col = getattr(subq.c, pk_column.key)
    ord_col = getattr(subq.c, order_column.key)
    rn = func.row_number().over(order_by=ord_col.desc() if desc else ord_col.asc()).label("rn")
    with_rn = select(pk_col.label("pk"), rn).select_from(subq).subquery("w")
    offset = (page - 1) * page_size
    end = offset + page_size
    ids_stmt = select(with_rn.c.pk).where(with_rn.c.rn > offset).where(with_rn.c.rn <= end)
    ids = [row[0] for row in session.execute(ids_stmt).all()]
    if not ids:
        return [], total
    items = base_query.filter(pk_column.in_(ids)).order_by(order_column.desc() if desc else order_column.asc()).all()
    return items, total
