from fastapi import APIRouter
from app.api.v1.endpoints import auth, users, agents, meters, readings, assignments, approvals, regions, files, reports

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(agents.router, prefix="/agents", tags=["Agents"])
api_router.include_router(meters.router, prefix="/meters", tags=["Meters"])
api_router.include_router(readings.router, prefix="/readings", tags=["Meter Readings"])
api_router.include_router(assignments.router, prefix="/assignments", tags=["Assignments"])
api_router.include_router(approvals.router, prefix="/approvals", tags=["Approvals"])
api_router.include_router(regions.router, prefix="/regions", tags=["Regions"])
api_router.include_router(files.router, prefix="/files", tags=["File Management"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
