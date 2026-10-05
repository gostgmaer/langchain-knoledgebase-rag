# Router upload jobs
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from packages.api.dependencies import (
    DEFAULT_TENANT_ID,
    get_scoped_container,
    require_uuid_header,
    require_admin,
    require_permission,
)
from packages.api.permissions import Permission
from packages.api.responses import ApiResponse
from packages.api.schemas.upload_job import UploadJobListResponseSchema, UploadJobResponseSchema
from packages.infrastructure.container import ApplicationContainer

router = APIRouter(
    prefix="/upload-jobs",
    tags=["Upload Jobs"],
    dependencies=[Depends(require_admin()), Depends(require_permission(Permission.UPLOAD_JOBS_READ))],
)


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[UploadJobListResponseSchema],
    summary="List upload jobs",
    description="Lists the calling tenant's upload jobs, most recent first, any status.",
)
async def list_upload_jobs(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)

    upload_jobs = container.repositories.upload_job()

    total = await upload_jobs.count_by_tenant(tenant_id)
    rows = await upload_jobs.list_by_tenant(tenant_id, limit=limit, offset=offset)

    return ApiResponse(
        message="Upload jobs retrieved.",
        data=UploadJobListResponseSchema(
            total=total,
            limit=limit,
            offset=offset,
            upload_jobs=[UploadJobResponseSchema.model_validate(j) for j in rows],
        ),
    )


@router.get(
    "/{upload_job_id}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[UploadJobResponseSchema],
    summary="Poll an upload's real pipeline progress",
    description=(
        "Tracks one document upload's queued/running/succeeded/failed "
        "status. The id is returned as `upload_job_id` from "
        "POST /api/v1/documents. Distinct from Document.status: this "
        "reflects the actual job (arq, or the in-process fallback), not "
        "just the document row's own state."
    ),
)
async def get_upload_job(
    upload_job_id: UUID,
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)

    upload_jobs = container.repositories.upload_job()
    upload_job = await upload_jobs.get(upload_job_id)

    if upload_job is None or upload_job.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload job not found.",
        )

    return ApiResponse(
        message="Upload job retrieved.",
        data=UploadJobResponseSchema.model_validate(upload_job),
    )
