import itertools
import os
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
            async with aiohttp.ClientSession(trust_env=True) as sess:
                with open("raw_result.txt", mode="a", encoding="utf-8-sig")as result_file:
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
    print("resaving")
    if res_saving_mode == "1":
        with open("raw_result.txt", "r", encoding='utf-8-sig')as rawr_f:
            with open("result.txt", "a", encoding="utf-8-sig")as r_f:
                text_list = rawr_f.readlines()
                pattern = "iter_n;"
                for c in range(1, len(text_list)+1):
                    for line in text_list:
                        splited_line = line.split(pattern)
                        if splited_line[0] == str(c):
                            r_f.write(splited_line[1])
    elif res_saving_mode == "2":
        with open("raw_result.txt", "r", encoding='utf-8-sig') as rawr_f:
            with open("result.txt", "a", encoding="utf-8-sig") as r_f:
                text_list = rawr_f.read()
                pattern = "iter_n;"
                text_list = text_list.split(text_separator)
                for c in range(1, len(text_list) + 1):
                    for line in text_list:
                        splited_line = line.split(pattern)
                        if splited_line[0] == str(c):
                            text = splited_line[1] + text_separator
                            if c != 1:
                                text = "\n" + text
                            r_f.write(text)


async def prompt(prompt_r, sess, model, x_of_res, iter_n, path_to_prompt_f, content_type, progress_f,
                 result_file, text_separator="*&*", res_saving_mode="1"):
    try:
        print(f"func num: {iter_n} started at {time.strftime('%X')}")
        headers = {
            "Authorization": f"Bearer {config.API_KEY}",
            "openai-version": "2020-10-01",
            "Content-Type": "application/json"
        }
        # Make request and extract data
        if content_type == "text" or content_type == "img":
            if content_type == "text":
                while True:
                    try:
                        url = "https://api.openai.com/v1/chat/completions"
                        data = {
                                "model": f"{model}",
                                "messages": [
                                    {"role": "system", "content": f"{prompt_r.split(':')[0]}"},
                                    {"role": "user", "content": f"{prompt_r.split(':')[1]}"}
                                ],
                            }

                        data_in_bytes = json.dumps(data, indent=2).encode('utf-8')

                        async with sess.post(url=url, headers=headers, data=data_in_bytes) as resp:
                            if resp.status != 200:
                                continue
                            json_bytes = bytes()
                            async for line in resp.content:
                                json_bytes = json_bytes + line
                            json_content = json.loads(json_bytes)
                            try:
                                resp_msg = json_content.get("choices")[0].get("message").get("content")
                                print(iter_n)
                            except TypeError:
                                await asyncio.sleep(5)
                                continue
                            if res_saving_mode == "1":
                                resp_text = f"{iter_n}iter_n;" + prompt_r + resp_msg + text_separator
                            elif res_saving_mode == "2":
                                resp_text = f"{iter_n}iter_n;" + resp_msg.replace("\n", text_separator) + '\n'
                            lock = asyncio.Lock()
                            async with lock:
                                blocked_write_in_the_end_of_file(f=result_file, value=resp_text)
                            break
                    except Exception as err:
                        print(err)
                        await asyncio.sleep(5)
                        continue

                # Extract IMG
            elif content_type == "img":
                y = 0
                while y < x_of_res:
                    try:
                        url = "https://api.openai.com/v1/images/generations"
                        data = {
                            "model": f"{model}",
                            "prompt": f"{prompt_r}",
                            "n": 1,
                            "quality": "Standart",
                            "size": "1024x1024",
                        }

                        data_in_bytes = json.dumps(data, indent=2).encode('utf-8')
                        async with sess.post(url=url, headers=headers, data=data_in_bytes) as resp:
                            json_bytes = bytes()
                            async for line in resp.content:
                                json_bytes = json_bytes + line
                            json_content = json.loads(json_bytes)
                            try:
                                resp_img_url = json_content.get("data")[0].get("url")
                            except TypeError:
                                await asyncio.sleep(10)
                                continue
                            print(resp_img_url)
                        async with sess.get(url=resp_img_url) as resp:
                            path_to_img_dir = f"imgs/{iter_n}_iter"
                            if not os.path.exists(path=path_to_img_dir):
                                os.mkdir(path=path_to_img_dir)
                            async with aiofiles.open(f"{path_to_img_dir}/img{iter_n}-variation{y+1}.png", "wb")as img_file:
                                await img_file.write(await resp.read())
                            y = y + 1
                    except aiohttp.ClientHttpProxyError:
                        continue
            loop = asyncio.get_event_loop()
            lock = asyncio.Lock()
            async with lock:
                blocked_write_in_the_end_of_file(f=progress_f, value=f"{iter_n}\n")
            await loop.run_in_executor(None, blocked_write_in_the_end_of_file, progress_f, f"{iter_n}\n")
            print(f"func num: {iter_n} finished at {time.strftime('%X')}")
        else:
            return 1
    finally:
        print("e")


def blocked_write_in_the_end_of_file(f, value):
    f.write(value)


def run_main():
    asyncio.set_event_loop_policy(MyPolicy())  # If on Windows
    logging.basicConfig(filename="log.log", level=logging.ERROR)

    asyncio.run(main(text_separator=config.text_separator, content_type=config.req_type, model=config.model_name,
                     res_saving_mode=config.result_saving_mode, path_to_prompt_f=config.path_to_prompt_file,
                     x_of_res=config.num_of_res))


run_main()
