import asyncio
import character


async def main():
    info = await character.get_info(
        "9BxfSzn-igwmY62Ob8CBvcW57JyeBPRKx6PQCk33YUk%3D", 1013)
    print(info)
    await character.close()


asyncio.run(main())