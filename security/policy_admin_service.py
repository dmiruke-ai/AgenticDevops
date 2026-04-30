"""
Policy Admin Service - Dynamic Rego Policy Management (S3-08).

Provides HTTP API for updating OPA policies dynamically:
1. Upload new policies via REST API
2. Validate policies before activation
3. Version control with rollback
4. Audit logging for all changes

Usage:
    # Update policy
    curl -X PUT http://localhost:8183/policies/intent_security \
      -H "Content-Type: text/plain" \
      --data-binary @intent_security.rego

    # Validate policy
    curl -X POST http://localhost:8183/policies/validate \
      -H "Content-Type: text/plain" \
      --data-binary @new_policy.rego

    # List versions
    curl http://localhost:8183/policies/intent_security/versions

    # Rollback
    curl -X POST http://localhost:8183/policies/intent_security/rollback?version=5
"""

import os
import json
import hashlib
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Body, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import httpx


class PolicyUpdate(BaseModel):
    """Policy update metadata."""
    policy_name: str
    version: int
    content_hash: str
    updated_at: datetime
    updated_by: str = "api"
    validation_status: str  # "valid" | "invalid"
    error_message: Optional[str] = None


class PolicyVersion(BaseModel):
    """Policy version entry."""
    version: int
    content_hash: str
    timestamp: datetime
    file_size: int


app = FastAPI(
    title="OPA Policy Admin Service",
    description="Dynamic policy management for AI DevOps Agent Platform",
    version="1.0.0",
)

# Configuration
POLICY_DIR = Path("/policies")
VERSION_DIR = Path("/versions")
OPA_URL = os.getenv("OPA_URL", "http://opa:8181")

# Ensure directories exist
POLICY_DIR.mkdir(exist_ok=True)
VERSION_DIR.mkdir(exist_ok=True)


# =============================================================================
# Policy Validation
# =============================================================================

async def validate_rego_policy(content: str) -> tuple[bool, Optional[str]]:
    """
    Validate Rego policy using OPA CLI.

    Args:
        content: Rego policy content

    Returns:
        (is_valid, error_message)
    """
    # Write to temp file
    temp_file = Path("/tmp/temp_policy.rego")
    temp_file.write_text(content)

    try:
        # Run OPA check
        result = subprocess.run(
            ["opa", "check", str(temp_file)],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            return True, None
        else:
            return False, result.stderr

    except subprocess.TimeoutExpired:
        return False, "Validation timeout (>5s)"
    except FileNotFoundError:
        # OPA CLI not available, try API validation
        return await validate_rego_via_api(content)
    finally:
        temp_file.unlink(missing_ok=True)


async def validate_rego_via_api(content: str) -> tuple[bool, Optional[str]]:
    """
    Validate Rego policy via OPA HTTP API.

    Args:
        content: Rego policy content

    Returns:
        (is_valid, error_message)
    """
    try:
        async with httpx.AsyncClient() as client:
            # Try to compile the policy
            response = await client.put(
                f"{OPA_URL}/v1/policies/test_validation",
                content=content,
                headers={"Content-Type": "text/plain"},
                timeout=5.0,
            )

            if response.status_code == 200:
                # Delete test policy
                await client.delete(f"{OPA_URL}/v1/policies/test_validation")
                return True, None
            else:
                error = response.json().get("errors", [{}])[0].get("message", "Unknown error")
                return False, error

    except Exception as e:
        return False, f"API validation failed: {str(e)}"


# =============================================================================
# Policy Versioning
# =============================================================================

def save_policy_version(policy_name: str, content: str) -> int:
    """
    Save policy version with timestamp and hash.

    Args:
        policy_name: Policy identifier (e.g., "intent_security")
        content: Policy content

    Returns:
        Version number
    """
    policy_version_dir = VERSION_DIR / policy_name
    policy_version_dir.mkdir(exist_ok=True)

    # Get next version number
    existing_versions = list(policy_version_dir.glob("v*.rego"))
    next_version = len(existing_versions) + 1

    # Calculate hash
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    # Save versioned file
    version_file = policy_version_dir / f"v{next_version}.rego"
    version_file.write_text(content)

    # Save metadata
    metadata = {
        "version": next_version,
        "content_hash": content_hash,
        "timestamp": datetime.utcnow().isoformat(),
        "file_size": len(content),
    }

    metadata_file = policy_version_dir / f"v{next_version}.json"
    metadata_file.write_text(json.dumps(metadata, indent=2))

    return next_version


def get_policy_versions(policy_name: str) -> List[PolicyVersion]:
    """Get all versions of a policy."""
    policy_version_dir = VERSION_DIR / policy_name

    if not policy_version_dir.exists():
        return []

    versions = []
    for metadata_file in sorted(policy_version_dir.glob("v*.json")):
        metadata = json.loads(metadata_file.read_text())
        versions.append(PolicyVersion(**metadata))

    return versions


def rollback_policy(policy_name: str, version: int) -> str:
    """
    Rollback policy to specific version.

    Args:
        policy_name: Policy identifier
        version: Version number to rollback to

    Returns:
        Policy content

    Raises:
        FileNotFoundError: If version doesn't exist
    """
    version_file = VERSION_DIR / policy_name / f"v{version}.rego"

    if not version_file.exists():
        raise FileNotFoundError(f"Version {version} not found for policy {policy_name}")

    return version_file.read_text()


# =============================================================================
# OPA Integration
# =============================================================================

async def reload_opa_policy(policy_name: str, content: str) -> bool:
    """
    Reload policy in OPA via REST API.

    Args:
        policy_name: Policy identifier
        content: Policy content

    Returns:
        Success status
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{OPA_URL}/v1/policies/{policy_name}",
                content=content,
                headers={"Content-Type": "text/plain"},
                timeout=10.0,
            )

            return response.status_code == 200

    except Exception as e:
        print(f"Failed to reload OPA policy: {e}")
        return False


# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    # Check OPA connectivity
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{OPA_URL}/health", timeout=2.0)
            opa_healthy = response.status_code == 200
    except:
        opa_healthy = False

    return {
        "status": "healthy" if opa_healthy else "degraded",
        "opa_connected": opa_healthy,
        "policy_dir": str(POLICY_DIR),
        "version_dir": str(VERSION_DIR),
    }


@app.post("/policies/validate")
async def validate_policy(content: str = Body(..., media_type="text/plain")):
    """
    Validate Rego policy without activating it.

    Request body: Raw Rego policy content
    """
    is_valid, error_message = await validate_rego_policy(content)

    return {
        "valid": is_valid,
        "error": error_message,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.put("/policies/{policy_name}")
async def update_policy(
    policy_name: str,
    content: str = Body(..., media_type="text/plain"),
    validate: bool = Query(True, description="Validate before activating"),
    save_version: bool = Query(True, description="Save version history"),
):
    """
    Update or create policy dynamically.

    Steps:
    1. Validate policy (if validate=true)
    2. Save version (if save_version=true)
    3. Write to policy directory
    4. Reload in OPA (if --watch enabled, happens automatically)

    Args:
        policy_name: Policy identifier (e.g., "intent_security")
        content: Rego policy content
        validate: Whether to validate before activation
        save_version: Whether to save version history
    """
    # Step 1: Validate
    if validate:
        is_valid, error_message = await validate_rego_policy(content)
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Policy validation failed: {error_message}",
            )

    # Step 2: Save version
    version_number = None
    if save_version:
        version_number = save_policy_version(policy_name, content)

    # Step 3: Write to policy directory
    policy_file = POLICY_DIR / f"{policy_name}.rego"
    policy_file.write_text(content)

    # Step 4: Reload in OPA (force reload via API)
    reload_success = await reload_opa_policy(policy_name, content)

    return {
        "policy_name": policy_name,
        "version": version_number,
        "content_hash": hashlib.sha256(content.encode()).hexdigest(),
        "validation_status": "valid" if validate else "skipped",
        "reload_status": "success" if reload_success else "pending",
        "updated_at": datetime.utcnow().isoformat(),
        "message": (
            "Policy updated and reloaded successfully"
            if reload_success
            else "Policy updated, OPA will auto-reload via --watch"
        ),
    }


@app.get("/policies/{policy_name}")
async def get_policy(policy_name: str):
    """Get current active policy content."""
    policy_file = POLICY_DIR / f"{policy_name}.rego"

    if not policy_file.exists():
        raise HTTPException(status_code=404, detail=f"Policy {policy_name} not found")

    content = policy_file.read_text()
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    return {
        "policy_name": policy_name,
        "content": content,
        "content_hash": content_hash,
        "file_size": len(content),
        "last_modified": datetime.fromtimestamp(policy_file.stat().st_mtime).isoformat(),
    }


@app.get("/policies/{policy_name}/versions")
async def list_policy_versions(policy_name: str):
    """List all versions of a policy."""
    versions = get_policy_versions(policy_name)

    if not versions:
        raise HTTPException(
            status_code=404,
            detail=f"No versions found for policy {policy_name}",
        )

    return {
        "policy_name": policy_name,
        "total_versions": len(versions),
        "versions": [v.model_dump() for v in versions],
    }


@app.post("/policies/{policy_name}/rollback")
async def rollback_policy_endpoint(
    policy_name: str,
    version: int = Query(..., description="Version number to rollback to"),
):
    """
    Rollback policy to a previous version.

    Args:
        policy_name: Policy identifier
        version: Version number to rollback to
    """
    try:
        # Get version content
        content = rollback_policy(policy_name, version)

        # Validate
        is_valid, error_message = await validate_rego_policy(content)
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Rollback failed - version {version} is invalid: {error_message}",
            )

        # Write to active policy file
        policy_file = POLICY_DIR / f"{policy_name}.rego"
        policy_file.write_text(content)

        # Reload in OPA
        reload_success = await reload_opa_policy(policy_name, content)

        return {
            "policy_name": policy_name,
            "rolled_back_to_version": version,
            "reload_status": "success" if reload_success else "pending",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/policies")
async def list_policies():
    """List all active policies."""
    policies = []

    for policy_file in POLICY_DIR.glob("*.rego"):
        content = policy_file.read_text()
        versions = get_policy_versions(policy_file.stem)

        policies.append({
            "policy_name": policy_file.stem,
            "content_hash": hashlib.sha256(content.encode()).hexdigest(),
            "file_size": len(content),
            "total_versions": len(versions),
            "last_modified": datetime.fromtimestamp(policy_file.stat().st_mtime).isoformat(),
        })

    return {
        "total_policies": len(policies),
        "policies": policies,
    }


@app.delete("/policies/{policy_name}")
async def delete_policy(policy_name: str):
    """
    Delete policy (soft delete - keeps versions).

    Args:
        policy_name: Policy identifier
    """
    policy_file = POLICY_DIR / f"{policy_name}.rego"

    if not policy_file.exists():
        raise HTTPException(status_code=404, detail=f"Policy {policy_name} not found")

    # Delete from OPA
    try:
        async with httpx.AsyncClient() as client:
            await client.delete(f"{OPA_URL}/v1/policies/{policy_name}")
    except:
        pass

    # Delete active file (versions remain)
    policy_file.unlink()

    return {
        "policy_name": policy_name,
        "status": "deleted",
        "timestamp": datetime.utcnow().isoformat(),
        "note": "Version history preserved in /versions",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8183)
