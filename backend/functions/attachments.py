from core import serialize_json
from database.database import Database


async def create_experiment_attachment(
    experiment_id: str,
    uploaded_by: str | None,
    original_filename: str,
    stored_filename: str,
    content_type: str,
    size_bytes: int,
    description: str | None = None,
) -> dict | None:
    async with Database() as db:
        await db.execute(
            """INSERT INTO experiment_attachments
                   (experiment_id, uploaded_by, original_filename, stored_filename,
                    content_type, size_bytes, description)
               VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            (
                experiment_id,
                uploaded_by,
                original_filename,
                stored_filename,
                content_type,
                size_bytes,
                description,
            ),
        )
        row = await db.execute(
            """SELECT id, experiment_id, uploaded_by, original_filename, stored_filename,
                      content_type, size_bytes, description, created_at
               FROM experiment_attachments
               WHERE stored_filename = $1""",
            (stored_filename,),
        )
        return serialize_json(row)


async def list_experiment_attachments(experiment_id: str) -> list[dict]:
    async with Database() as db:
        rows = await db.execute_all(
            """SELECT a.id, a.experiment_id, a.uploaded_by, a.original_filename,
                      a.content_type, a.size_bytes, a.description, a.created_at,
                      u.email AS uploaded_by_email
               FROM experiment_attachments a
               LEFT JOIN users u ON u.id = a.uploaded_by
               WHERE a.experiment_id = $1
               ORDER BY a.created_at DESC""",
            (experiment_id,),
        )
        return serialize_json(rows or [])


async def get_experiment_attachment(experiment_id: str, attachment_id: str) -> dict | None:
    async with Database() as db:
        row = await db.execute(
            """SELECT id, experiment_id, uploaded_by, original_filename, stored_filename,
                      content_type, size_bytes, description, created_at
               FROM experiment_attachments
               WHERE experiment_id = $1 AND id = $2""",
            (experiment_id, attachment_id),
        )
        return serialize_json(row)


async def delete_experiment_attachment(experiment_id: str, attachment_id: str) -> dict | None:
    async with Database() as db:
        row = await db.execute(
            """SELECT id, experiment_id, uploaded_by, original_filename, stored_filename,
                      content_type, size_bytes, description, created_at
               FROM experiment_attachments
               WHERE experiment_id = $1 AND id = $2""",
            (experiment_id, attachment_id),
        )
        if not row:
            return None
        await db.execute(
            "DELETE FROM experiment_attachments WHERE experiment_id = $1 AND id = $2",
            (experiment_id, attachment_id),
        )
        return serialize_json(row)
