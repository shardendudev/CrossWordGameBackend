import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models.user import User
from app.core.auth import get_current_user,get_current_token_claims
from app.schemas.user import UserCreate, UserResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def createUser(
    payload: UserCreate,
    claims: dict=Depends(get_current_token_claims),
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """
    Registers a new player profile with default skill level (0.200) and hint balance.
    """
    verified_uid = claims.get("user_id") or claims.get("sub")
    token_email = claims.get("email") or payload.email
    logger.info("Processing user profile for user_id '%s', username '%s'", payload.user_id, payload.username)
    # Check if username is already taken
   
    existing_user_res = await db.execute(select(User).where(User.user_id == verified_uid))
    existing_user = existing_user_res.scalars().first();
    if existing_user:
        logger.warning("User with user_id '%s' already exists. Returning profile.", payload.user_id)
        return existing_user;

    # Prevent username collision: check if someone else already using this username
    username_res = await db.execute(select(User).where(User.username == payload.username))
    if username_res.scalars().first():
        logger.warning("Registration failed: Username '%s' is already registered by another user.", payload.username)
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{payload.username}' is already registered."
        )

    #create the new user profile    
    user = User(
        user_id = verified_uid,
        username=payload.username,
        email = token_email,
        current_skill_level=0.200,
        total_games_played=0,
        premium_hints_balance=5
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info("User '%s' created successfully with user_id='%s'", user.username, user.user_id)
    return user



@router.post("/login", response_model=UserResponse)
async def loginUser(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """
    Logs in an existing player by username, or automatically registers them if they don't exist.
    """
    result = await db.execute(select(User).where(User.username == payload.username))
    user = result.scalars().first()
    if not user:
        user = User(
            username=payload.username,
            current_skill_level=0.200,
            total_games_played=0,
            premium_hints_balance=5
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


@router.get("/by-username/{username}", response_model=UserResponse)
async def getUserByUsername(
    username: str,
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """
    Fetches player profile details by username.
    """
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with username '{username}' not found."
        )
    return user


@router.get("/me",response_model=UserResponse)
async def getMyProfile(
    current_user: User = Depends(get_current_user)
) -> UserResponse:
    return current_user
    

@router.get("/{user_id}", response_model=UserResponse)
async def getUserProfile(
    user_id: str,
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """
    Fetches player profile details by UUID.
    """
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID '{user_id}' not found."
        )
    return user

