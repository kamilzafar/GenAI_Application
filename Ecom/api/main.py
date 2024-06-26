from uuid import UUID, uuid4
from fastapi import FastAPI, Depends, HTTPException, status, Body
from sqlmodel import select, Session
from typing import List, Annotated, Optional
from app.api.utils.settings import REFRESH_TOKEN_EXPIRE_MINUTES, SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from datetime import timedelta
from app.api.utils.services import create_order, create_product_cart, delete_cart_product, get_current_user, get_user_by_username, update_cart, user_cart, verify_password, create_access_token, signup_user
from app.api.utils.models import Cart, CartCreate, OrderCreate, OrderDelete, OrderUpdate, Product, TokenData, Token, Order, User, UserCreate, Userlogin
from app.api.utils.db import lifespan, db_session
from app.api.utils.openai import create_thread, generate_message, get_response, user_chat

SECRET_KEY = str(SECRET_KEY)
ALGORITHM = ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = ACCESS_TOKEN_EXPIRE_MINUTES

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI(title="E-commerce API", version="0.1.0", lifespan=lifespan)


@app.post("/api/login", response_model=Token)
async def login_for_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: Annotated[Session, Depends(db_session)]) -> Token:
    user: Userlogin = get_user_by_username(db, form_data.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    refresh_token_expires = timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    refresh_token = create_access_token(
        data={"sub": user.username}, expires_delta=refresh_token_expires
    )
    return {"access_token": access_token, "refresh_token": refresh_token, "expires_in": access_token_expires+refresh_token_expires, "token_type": "bearer"}

@app.post("/api/signup", response_model=User)
async def signup(db: Annotated[Session, Depends(db_session)], user: UserCreate ):
    try:
        return signup_user(user, db)
    except Exception as e:
        raise HTTPException(status_code=400,detail=str(e))

@app.get("/api/users/me", response_model=User)
async def read_users_me(token: Annotated[str, Depends(oauth2_scheme)], db: Annotated[Session, Depends(db_session)]) -> User:
    user = await get_current_user(token, db)
    return user

@app.get("/api/products", response_model=List[Product])
def get_products(session: Annotated[Session, Depends(db_session)], query: Optional[str] = None) -> List[Product]:
    if query:
        products = session.exec(select(Product).where(Product.slug.contains(query))).all()
    else:
        products = session.exec(select(Product)).all()
    return products

@app.get("/api/products/{product_slug}", response_model=Product)
def get_product(product_slug: str, session: Annotated[Session, Depends(db_session)]) -> Product:
    product = session.exec(select(Product).filter(Product.slug == product_slug)).first()
    return product

@app.get("/api/product", response_model=Product)
def get_product_by_id(product_id: UUID, session: Annotated[Session, Depends(db_session)]) -> Product:
    product = session.exec(select(Product).where(Product.sku == product_id)).first()
    return product

@app.get("/api/cart", response_model=List[Cart])
def get_cart(session: Annotated[Session, Depends(db_session)], user: Annotated[User, Depends(get_current_user)]) -> List[Cart]:
    cart = user_cart(session, user)
    return cart

@app.post("/api/cart", response_model=Cart)
def post_cart(cart: CartCreate, session: Annotated[Session, Depends(db_session)], user: Annotated[User, Depends(get_current_user)]) -> Cart:
    cart = create_product_cart(session, cart, user)
    return cart

@app.patch("/api/cart", response_model=Cart)
def patch_cart(cart: CartCreate, session: Annotated[Session, Depends(db_session)], user: Annotated[User, Depends(get_current_user)]) -> Cart:
    updated_cart = update_cart(session, cart, user)
    return updated_cart

@app.delete("/api/cart", response_model=dict[str, str])
def delete_cart(cart: CartCreate, session: Annotated[Session, Depends(db_session)], user: Annotated[User, Depends(get_current_user)]) -> dict[str, str]:
    delete_cart_product(session, cart, user)
    return {"message": "Product removed from cart"}

@app.post("/api/order", response_model=Order)
def post_order(order: OrderCreate, session: Annotated[Session, Depends(db_session)], user: Annotated[User, Depends(get_current_user)]) -> Order:
    new_order = create_order(session, order, user)
    return new_order

@app.get("/api/orders", response_model=List[Order])
def get_orders(user: Annotated[User, Depends(get_current_user)],session: Annotated[Session, Depends(db_session)]):
    orders = session.exec(select(Order).where(Order.user_id == user.id)).all()
    return orders

# @app.post("/api/openai")
# def openai(prompt: str) -> dict:
#     messages = generate_message(prompt)
#     return {"message": messages}

@app.delete("/api/order", response_model=dict[str, str])
def cancel_order(order: OrderDelete, session: Annotated[Session, Depends(db_session)], user: Annotated[User, Depends(get_current_user)]) -> dict[str, str]:
    cancel_order(session, order, user)
    return {"message": "Order cancelled"}

@app.patch("/api/order", response_model=Order)
def update_order(order: OrderUpdate, session: Annotated[Session, Depends(db_session)], user: Annotated[User, Depends(get_current_user)]) -> Order:
    updated_order = update_order(session, order, user)
    return updated_order

@app.post("/api/openai/start")
def start_a_conversation():
    thread = create_thread()
    return thread

# @app.post("/api/openai/messages")
# async def message(prompt: str, thread_id: str) -> dict:
#     response = await generate_message(prompt, thread_id)
#     return {"message": response}

@app.post("/api/messages")
async def message(prompt: str, thread_id: str):
    response = await user_chat(thread_id, prompt)
    return response

@app.get("/api/openai/getmessages")
def messages(thread_id: str):
    messages = get_response(thread_id)
    return {"messages": messages}