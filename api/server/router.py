"""
Routes for server management.
"""

import orjson as json
from fastapi import APIRouter, Depends, HTTPException, status
from starlette.responses import StreamingResponse
from sqlalchemy import select, exists, or_
from sqlalchemy.ext.asyncio import AsyncSession
from api.database import get_db_session
from api.config import k8s_core_client, settings
from api.auth import authorize
from api.server.schemas import Server, ServerArgs
from api.server.util import bootstrap_server

router = APIRouter()


@router.get("/")
async def list_servers(
    db: AsyncSession = Depends(get_db_session),
    _: None = Depends(authorize(allow_miner=True, purpose="management")),
):
    """
    List servers, this can be quite a large response...
    """
    return (await db.execute(select(Server))).unique().scalars().all()


@router.post("/")
async def create_server(
    server_args: ServerArgs,
    db: AsyncSession = Depends(get_db_session),
    _: None = Depends(authorize(allow_miner=True, allow_validator=False)),
):
    """
    Add a new server/kubernetes node to our inventory.  This is a very
    slow/long-running response via SSE, since it needs to do a lot of things.
    """
    node = k8s_core_client().read_node(name=server_args.name)
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No kubernetes node with name={server_args.name} found!",
        )
    if (await db.execute(select(exists().where(Server.name == server_args.name)))).scalar():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Server with name={server_args.name} is already provisioned!",
        )

    # Stream creation/provisioning details back as they occur.
    async def _stream_provisioning_status():
        async for chunk in bootstrap_server(node, server_args):
            yield chunk

    return StreamingResponse(_stream_provisioning_status())


@router.delete("/{id_or_name}")
async def delete_server(
    id_or_name: str,
    db: AsyncSession = Depends(get_db_session),
    _: None = Depends(authorize(allow_miner=True, allow_validator=False, purpose="management")),
):
    """
    Remove a kubernetes node from the cluster.
    """
    server = (
        (
            await db.execute(
                select(Server).where(or_(Server.name == id_or_name, Server.server_id == id_or_name))
            )
        )
        .unique()
        .scalar_one_or_none()
    )
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No kubernetes node with id or name {id_or_name} found!",
        )

    await settings.redis_client.publish(
        "miner_events",
        json.dumps(
            {
                "event_type": "server_deleted",
                "event_data": {
                    "server_id": server.server_id,
                },
            }
        ).decode(),
    )
    return {
        "status": "started",
        "detail": f"Deletion of {server.name=} {server.server_id=} started, and will be processed asynchronously by gepetto.",
    }
