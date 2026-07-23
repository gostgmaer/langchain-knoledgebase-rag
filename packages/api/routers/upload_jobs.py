# Router upload jobs
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from packages.api.dependencies import (
    DEFAULT_TENANT_ID,
    get_scoped_container,
    require_uuid_header,
)
from packages.api.responses import ApiResponse
from packages.api.schemas.upload_job import UploadJobResponseSchema
from packages.infrastructure.container import ApplicationContainer

router = APIRouter(
    prefix="/upload-jobs",
    tags=["Upload Jobs"],
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
