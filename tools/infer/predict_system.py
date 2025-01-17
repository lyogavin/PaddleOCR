# Copyright (c) 2020 PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os
import sys
import subprocess
import tqdm
import glob
from random import shuffle



__dir__ = os.path.dirname(os.path.abspath(__file__))
sys.path.append(__dir__)
sys.path.insert(0, os.path.abspath(os.path.join(__dir__, '../..')))

os.environ["FLAGS_allocator_strategy"] = 'auto_growth'

import cv2
import copy
import numpy as np
import json
import time
import logging
from PIL import Image

from ppocr.utils.logging import get_logger

ts=int(time.time())
print(f"logging to {ts}_{os.getpid()}_log.log")
logger = get_logger(log_file=f"logs/{ts}_{os.getpid()}_log.log")


import tools.infer.utility as utility
import tools.infer.predict_rec as predict_rec
import tools.infer.predict_det as predict_det
import tools.infer.predict_cls as predict_cls
#from ppocr.utils.utility import get_image_file_list, check_and_read
from ppocr.utils.utility import check_and_read

from tools.infer.utility import draw_ocr_box_txt, get_rotate_crop_image
import datadog_sender


def _check_image_file(path):
    img_end = {'jpg', 'bmp', 'png', 'jpeg', 'rgb', 'tif', 'tiff', 'gif', 'pdf', 'jpe'}
    return any([path.lower().endswith(e) for e in img_end])


def get_image_file_list(img_file):
    imgs_lists = []
    if img_file is None or not os.path.exists(img_file):
        raise Exception("not found any img file in {}".format(img_file))

    img_end = {'jpg', 'bmp', 'png', 'jpeg', 'rgb', 'tif', 'tiff', 'gif', 'pdf', 'jpe'}
    if os.path.isfile(img_file) and _check_image_file(img_file):
        imgs_lists.append(img_file)
    elif os.path.isdir(img_file):
        os_list_files = list(os.listdir(img_file))
        for single_file in tqdm.tqdm(os_list_files, total=len(os_list_files)):
            file_path = os.path.join(img_file, single_file)
            if os.path.isfile(file_path) and _check_image_file(file_path):
                imgs_lists.append(file_path)
    if len(imgs_lists) == 0:
        raise Exception("not found any img file in {}".format(img_file))
    imgs_lists = sorted(imgs_lists)
    return imgs_lists

class TextSystem(object):
    def __init__(self, args):
        if not args.show_log:
            logger.setLevel(logging.INFO)

        self.text_detector = predict_det.TextDetector(args)
        self.text_recognizer = predict_rec.TextRecognizer(args)
        self.use_angle_cls = args.use_angle_cls
        self.drop_score = args.drop_score
        if self.use_angle_cls:
            self.text_classifier = predict_cls.TextClassifier(args)

        self.args = args
        self.crop_image_res_index = 0

    def draw_crop_rec_res(self, output_dir, img_crop_list, rec_res):
        os.makedirs(output_dir, exist_ok=True)
        bbox_num = len(img_crop_list)
        for bno in range(bbox_num):
            cv2.imwrite(
                os.path.join(output_dir,
                             f"mg_crop_{bno+self.crop_image_res_index}.jpg"),
                img_crop_list[bno])
            logger.debug(f"{bno}, {rec_res[bno]}")
        self.crop_image_res_index += bbox_num

    def __call__(self, img, cls=True):
        time_dict = {'det': 0, 'rec': 0, 'csl': 0, 'all': 0}
        start = time.time()
        ori_im = img.copy()
        dt_boxes, elapse = self.text_detector(img)
        time_dict['det'] = elapse
        logger.debug("dt_boxes num : {}, elapse : {}".format(
            len(dt_boxes), elapse))
        if dt_boxes is None:
            return None, None
        img_crop_list = []

        dt_boxes = sorted_boxes(dt_boxes)

        for bno in range(len(dt_boxes)):
            tmp_box = copy.deepcopy(dt_boxes[bno])
            img_crop = get_rotate_crop_image(ori_im, tmp_box)
            img_crop_list.append(img_crop)
        if self.use_angle_cls and cls:
            img_crop_list, angle_list, elapse = self.text_classifier(
                img_crop_list)
            time_dict['cls'] = elapse
            logger.debug("cls num  : {}, elapse : {}".format(
                len(img_crop_list), elapse))

        rec_res, elapse = self.text_recognizer(img_crop_list)
        time_dict['rec'] = elapse
        logger.debug("rec_res num  : {}, elapse : {}".format(
            len(rec_res), elapse))
        if self.args.save_crop_res:
            self.draw_crop_rec_res(self.args.crop_res_save_dir, img_crop_list,
                                   rec_res)
        filter_boxes, filter_rec_res = [], []
        for box, rec_result in zip(dt_boxes, rec_res):
            text, score = rec_result
            if score >= self.drop_score:
                filter_boxes.append(box)
                filter_rec_res.append(rec_result)
        end = time.time()
        time_dict['all'] = end - start
        return filter_boxes, filter_rec_res, time_dict


def sorted_boxes(dt_boxes):
    """
    Sort text boxes in order from top to bottom, left to right
    args:
        dt_boxes(array):detected text boxes with shape [4, 2]
    return:
        sorted boxes(array) with shape [4, 2]
    """
    num_boxes = dt_boxes.shape[0]
    sorted_boxes = sorted(dt_boxes, key=lambda x: (x[0][1], x[0][0]))
    _boxes = list(sorted_boxes)

    for i in range(num_boxes - 1):
        for j in range(i, 0, -1):
            if abs(_boxes[j + 1][0][1] - _boxes[j][0][1]) < 10 and \
                    (_boxes[j + 1][0][0] < _boxes[j][0][0]):
                tmp = _boxes[j]
                _boxes[j] = _boxes[j + 1]
                _boxes[j + 1] = tmp
            else:
                break
    return _boxes


def main(args):
    image_file_list = []
    for dir_entry in args.image_dir.split(","):
        print(f"getting file list for {dir_entry}")
        image_file_list_entry = get_image_file_list(dir_entry)
        image_file_list.extend(image_file_list_entry)

        print(f"len current file list: {len(image_file_list)}")
    file_name_set = set()

    print(f"files found in {args.image_dir}: len: {len(image_file_list)}")
    deduped_image_file_list = []

    for f in image_file_list:
        file_name = os.path.basename(f)
        if file_name not in file_name_set:
            file_name_set.add(file_name)
            deduped_image_file_list.append(f)

    image_file_list = deduped_image_file_list
    print(f"after dedup files found in {args.image_dir}: len: {len(image_file_list)}")



    image_file_list = image_file_list[args.process_id::args.total_process_num]

    text_sys = TextSystem(args)
    is_visualize = False
    save_results_per_file = True
    font_path = args.vis_font_path
    drop_score = args.drop_score
    draw_img_save_dir = args.draw_img_save_dir
    os.makedirs(draw_img_save_dir, exist_ok=True)
    save_results = []

    logger.info(
        "In PP-OCRv3, rec_image_shape parameter defaults to '3, 48, 320', "
        "if you are using recognition model with PP-OCRv2 or an older version, please set --rec_image_shape='3,32,320"
    )

    # warm up 10 times
    if args.warmup:
        img = np.random.uniform(0, 255, [640, 640, 3]).astype(np.uint8)
        for i in range(10):
            res = text_sys(img)

    total_time = 0
    cpu_mem, gpu_mem, gpu_util = 0, 0, 0
    _st = time.time()
    count = 0
    shuffle(image_file_list)
    print(f"top 10 files: {image_file_list[:10]}")
    for idx, image_file in enumerate(tqdm.tqdm(image_file_list, total=len(image_file_list))):
        datadog_sender.send_datadog_event("img_file_processed", [], f"pid:{os.getpid()}")

        # check existing....

        if os.path.exists(os.path.join(draw_img_save_dir, f"{os.path.basename(image_file)}_system_results.txt")):
            datadog_sender.send_datadog_event("img_file_results_existing", [], f"pid:{os.getpid()}")
            logger.debug(f"{image_file} exists, skipping")
            continue

        img, flag, _ = check_and_read(image_file)
        if not flag:
            img = cv2.imread(image_file)
        if img is None:
            logger.debug("error in loading image:{}".format(image_file))
            continue
        starttime = time.time()
        dt_boxes, rec_res, time_dict = text_sys(img)
        elapse = time.time() - starttime
        total_time += elapse

        logger.debug(
            str(idx) + "  Predict time of %s: %.3fs" % (image_file, elapse))
        for text, score in rec_res:
            logger.debug("{}, {:.3f}".format(text, score))

        res = [{
            "transcription": rec_res[idx][0],
            "score": rec_res[idx][1],
            "points": np.array(dt_boxes[idx]).astype(np.int32).tolist(),
        } for idx in range(len(dt_boxes))]
        save_pred = os.path.basename(image_file) + "\t" + json.dumps(
            res, ensure_ascii=False) + "\n"

        if save_results_per_file:
            with open(
                os.path.join(draw_img_save_dir, f"{os.path.basename(image_file)}_system_results.txt"),
                'w',
                encoding='utf-8') as f:
                f.writelines(save_pred)
            logger.debug("The ocr results saved in {}".format(
                os.path.join(draw_img_save_dir, f"{os.path.basename(image_file)}_system_results.txt")))
            datadog_sender.send_datadog_event("ocr_result_saved", [f"number of dt_boxes: {len(dt_boxes)}"], f"pid:{os.getpid()}")
        else:
            save_results.append(save_pred)

        if is_visualize:
            image = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            boxes = dt_boxes
            txts = [rec_res[i][0] for i in range(len(rec_res))]
            scores = [rec_res[i][1] for i in range(len(rec_res))]

            draw_img = draw_ocr_box_txt(
                image,
                boxes,
                txts,
                scores,
                drop_score=drop_score,
                font_path=font_path)
            if flag:
                image_file = image_file[:-3] + "png"
            cv2.imwrite(
                os.path.join(draw_img_save_dir, os.path.basename(image_file)),
                draw_img[:, :, ::-1])
            logger.debug("The visualized image saved in {}".format(
                os.path.join(draw_img_save_dir, os.path.basename(image_file))))

    logger.info("The predict total time is {}".format(time.time() - _st))
    if args.benchmark:
        text_sys.text_detector.autolog.report()
        text_sys.text_recognizer.autolog.report()

    if not save_results_per_file:
        with open(
                os.path.join(draw_img_save_dir, "system_results.txt"),
                'w',
                encoding='utf-8') as f:
            f.writelines(save_results)


if __name__ == "__main__":
    import random
    args = utility.parse_args()
    if args.use_mp:
        p_list = []
        total_process_num = args.total_process_num
        for process_id in range(total_process_num):
            time.sleep(random.randint(60, 120))
            print(f"starting process: {process_id}")
            cmd = [sys.executable, "-u"] + sys.argv + [
                "--process_id={}".format(process_id),
                "--use_mp={}".format(False)
            ]
            p = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stdout)
            p_list.append(p)
        for p in p_list:
            p.wait()
    else:
        main(args)
