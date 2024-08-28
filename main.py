import itertools
import os.path
import logging
import config
import time
import json
import asyncio
import aiohttp
import selectors
import aiofiles


class InvalidArgsGiven(Exception):
    pass


class MyPolicy(asyncio.DefaultEventLoopPolicy):
    def new_event_loop(self):
        selector = selectors.SelectSelector()
        return asyncio.SelectorEventLoop(selector)


async def main(text_separator, content_type, model, res_saving_mode, path_to_prompt_f, x_of_res):
    progress_list = []
    with open("progress.txt", "r+") as progress_f:
        lines_list = progress_f.readlines()
        for a in lines_list:
            progress_list.append(a.replace(" ", "").replace("\n", ""))
        with open(path_to_prompt_f, "r", encoding="utf-8") as f:
            async with aiohttp.ClientSession() as sess:
                with open("result.txt", "a", encoding="utf-8-sig")as result_file:
                    async with asyncio.TaskGroup() as taskgp:
                        for n, line_text in zip(itertools.count(1), f.readlines()):  # itertools.count(1)
                            is_el_in_progress = False
                            for o in progress_list:
                                if o == str(n):
                                    progress_list.remove(o)
                                    is_el_in_progress = True
                            if is_el_in_progress:
                                continue
                            task = taskgp.create_task(prompt(prompt_r=line_text, text_separator=text_separator,
                                                             sess=sess, content_type=content_type, model=model,
                                                             res_saving_mode=res_saving_mode,
                                                             path_to_prompt_f=path_to_prompt_f, iter_n=n,
                                                             x_of_res=x_of_res, progress_f=progress_f,
                                                             result_file=result_file))


async def prompt(prompt_r, sess, model, x_of_res, iter_n, path_to_prompt_f, content_type, progress_f, result_file,
                 text_separator="*&*", res_saving_mode="1"):
    try:
        print(f"func num: {iter_n} started at {time.strftime('%X')}")
        proxies = {
            'https': config.proxy_url,
            'http': config.proxy_url
        }
        proxy = config.proxy_url
        headers = {
            "Authorization": f"Bearer {config.API_KEY}",
            "openai-version": "2020-10-01",
            "Content-Type": "application/json"
        }
        proxy_url = "http://hvrNfVwr:Ld5ZnE9K@212.52.6.52:64384"

        # Make request and extract data
        if content_type == "text" or content_type == "img":
            if content_type == "text":
                while True:
                    url = "https://api.openai.com/v1/chat/completions"
                    data = {
                            "model": f"{model}",
                            "messages": [
                                {"role": "system", "content": f"{prompt_r.split(':')[0]}"},
                                {"role": "user", "content": f"{prompt_r.split(':')[1]}"}
                            ],
                        }

                    data_in_bytes = json.dumps(data, indent=2).encode('utf-8')

                    async with (sess.post(url=url, headers=headers, proxy=proxy_url, data=data_in_bytes) as resp):
                        if resp.status != 200:
                            continue
                        json_bytes = bytes()
                        async for line in resp.content:
                            json_bytes = json_bytes + line
                        json_content = json.loads(json_bytes)
                        try:
                            resp_msg = json_content.get("choices")[0].get("message").get("content")
                        except TypeError:
                            time.sleep(10)
                            continue
                        loop = asyncio.get_event_loop()
                        if res_saving_mode == "1":
                            resp_text = prompt_r + resp_msg + text_separator
                            await loop.run_in_executor(None, blocked_write_in_the_end_of_file, result_file,
                                                       resp_text)
                        elif res_saving_mode == "2":
                            resp_text = prompt_r.replace("\n", text_separator) + resp_msg.replace("\n", text_separator) + "\n"
                            await loop.run_in_executor(None, blocked_write_in_the_end_of_file, result_file,
                                                       resp_text)
                        else:
                            pass
                        break

                # Extract IMG
            elif content_type == "img":
                y = 0
                while y < x_of_res:
                    url = "https://api.openai.com/v1/images/generations"
                    data = {
                        "model": f"{model}",
                        "prompt": f"{prompt_r}",
                        "n": 1,
                        "quality": "Standart",
                        "size": "1024x1024",
                    }

                    data_in_bytes = json.dumps(data, indent=2).encode('utf-8')
                    async with sess.post(url=url, headers=headers, proxy=proxy_url, data=data_in_bytes) as resp:
                        json_bytes = bytes()
                        async for line in resp.content:
                            json_bytes = json_bytes + line
                        json_content = json.loads(json_bytes)
                        try:
                            resp_img_url = json_content.get("data")[0].get("url")
                        except TypeError:
                            time.sleep(10)
                            continue
                        print(resp_img_url)
                    async with sess.get(url=resp_img_url, proxy=proxy_url) as resp:
                        path_to_img_dir = f"imgs/{iter_n}_iter"
                        if not os.path.exists(path=path_to_img_dir):
                            os.mkdir(path=path_to_img_dir)
                        async with aiofiles.open(f"{path_to_img_dir}/img{iter_n}-variation{y+1}.png", "wb")as img_file:
                            await img_file.write(await resp.read())
                        y = y + 1
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, blocked_write_in_the_end_of_file, progress_f, f"{iter_n}\n")
            print(f"func num: {iter_n} finished at {time.strftime('%X')}")
        else:
            return 1
    except Exception as err:
        print(err)


def blocked_write_in_the_end_of_file(f, value):
    f.write(value)


def blocked_write_in_pos(f,)


def run_main():
    asyncio.set_event_loop_policy(MyPolicy())  # If on Windows
    logging.basicConfig(filename="log.log", level=logging.ERROR)

    asyncio.run(main(text_separator=config.text_separator, content_type=config.req_type, model=config.model_name,
                     res_saving_mode=config.result_saving_mode, path_to_prompt_f=config.path_to_prompt_file,
                     x_of_res=config.num_of_res))


run_main()
