from pydantic import BaseModel, Field


class TelegramUser(BaseModel):
    id: int
    is_bot: bool
    first_name: str
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None


class Chat(BaseModel):
    id: int
    type: str
    first_name: str | None = None
    username: str | None = None


class Message(BaseModel):
    message_id: int
    from_: TelegramUser | None = Field(None, alias="from")
    chat: Chat
    date: int
    text: str | None = None

    model_config = {"populate_by_name": True}


class CallbackQuery(BaseModel):
    id: str
    from_: TelegramUser = Field(alias="from")
    message: Message | None = None
    data: str | None = None

    model_config = {"populate_by_name": True}


class TelegramUpdate(BaseModel):
    update_id: int
    message: Message | None = None
    callback_query: CallbackQuery | None = None
