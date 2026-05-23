from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder


def success_response(message: str = "success", data=None, by_alias: bool = False):
    content = {
        "code": 200,
        "message": message,
        "data": data
    }

    return JSONResponse(content=jsonable_encoder(content, by_alias=by_alias))


