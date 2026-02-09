"""Prompt 保存路由"""

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import JSONResponse, RedirectResponse
import sqlite3

from app.dependencies import get_db_conn, require_auth
from app.services.prompts import (
    save_prompt, update_prompt, delete_prompt,
    get_user_prompts, get_prompt_by_id
)

router = APIRouter(prefix="/api/prompts", tags=["prompts"])


@router.get("")
def list_prompts(
    db: sqlite3.Connection = Depends(get_db_conn),
    current_user: dict = Depends(require_auth)
):
    """获取当前用户的所有保存 Prompt"""
    prompts = get_user_prompts(db, current_user["id"])
    return JSONResponse(content={
        "prompts": [dict(p) for p in prompts]
    })


@router.post("")
def create_prompt(
    request: Request,
    name: str = Form(...),
    prompt: str = Form(...),
    negative_prompt: str = Form(""),
    steps: int = Form(40),
    width: int = Form(1024),
    height: int = Form(768),
    db: sqlite3.Connection = Depends(get_db_conn),
    current_user: dict = Depends(require_auth)
):
    """保存新的 Prompt"""
    try:
        prompt_id = save_prompt(
            db, current_user["id"], name, prompt,
            negative_prompt, steps, width, height
        )
        db.commit()
        return JSONResponse(content={
            "success": True,
            "id": prompt_id,
            "message": "Prompt 已保存"
        })
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={"error": str(e)}
        )


@router.put("/{prompt_id}")
def edit_prompt(
    request: Request,
    prompt_id: int,
    name: str = Form(...),
    prompt: str = Form(...),
    negative_prompt: str = Form(""),
    steps: int = Form(40),
    width: int = Form(1024),
    height: int = Form(768),
    db: sqlite3.Connection = Depends(get_db_conn),
    current_user: dict = Depends(require_auth)
):
    """更新 Prompt"""
    try:
        success = update_prompt(
            db, prompt_id, current_user["id"], name, prompt,
            negative_prompt, steps, width, height
        )
        if not success:
            return JSONResponse(
                status_code=404,
                content={"error": "Prompt 不存在"}
            )
        db.commit()
        return JSONResponse(content={
            "success": True,
            "message": "Prompt 已更新"
        })
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={"error": str(e)}
        )


@router.delete("/{prompt_id}")
def remove_prompt(
    prompt_id: int,
    db: sqlite3.Connection = Depends(get_db_conn),
    current_user: dict = Depends(require_auth)
):
    """删除 Prompt"""
    success = delete_prompt(db, prompt_id, current_user["id"])
    if not success:
        return JSONResponse(
            status_code=404,
            content={"error": "Prompt 不存在"}
        )
    db.commit()
    return JSONResponse(content={
        "success": True,
        "message": "Prompt 已删除"
    })


@router.get("/{prompt_id}")
def get_prompt(
    prompt_id: int,
    db: sqlite3.Connection = Depends(get_db_conn),
    current_user: dict = Depends(require_auth)
):
    """获取单条 Prompt"""
    p = get_prompt_by_id(db, prompt_id, current_user["id"])
    if not p:
        return JSONResponse(
            status_code=404,
            content={"error": "Prompt 不存在"}
        )
    return JSONResponse(content={"prompt": dict(p)})
