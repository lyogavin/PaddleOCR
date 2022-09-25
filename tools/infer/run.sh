#paths = ["/home/ubuntu/cloudfs/ghost_data/newred_redbook_link_download/downloaded_images/*",
#         "/home/ubuntu/cloudfs/ghost_data/newred_redbook_link_download/downloaded_images/macbookpro13/downloaded_images.1/*",
#         "/home/ubuntu/cloudfs/ghost_data/newred_redbook_link_download/downloaded_images/aiwriter-fe002/downloaded_images/*",
#         "/home/ubuntu/cloudfs/ghost_data/newred_redbook_link_download/downloaded_images/aiwriter-fe003/downloaded_images/*",
#         "/home/ubuntu/cloudfs/ghost_data/newred_redbook_link_download/downloaded_images/cpu002/downloaded_images/*"]


nohup python tools/infer/predict_system.py --use_gpu=True --use_onnx=True --det_model_dir=./inference/det_onnx/model.onnx \
 --rec_model_dir=./inference/rec_onnx/model.onnx  --cls_model_dir=./inference/cls_onnx/model.onnx \
 --image_dir=/home/ubuntu/cloudfs/ghost_data/newred_redbook_link_download/downloaded_images,/home/ubuntu/cloudfs/ghost_data/newred_redbook_link_download/downloaded_images/aiwriter-fe003/downloaded_images,/home/ubuntu/cloudfs/ghost_data/newred_redbook_link_download/downloaded_images/aiwriter-fe002/downloaded_images,/home/ubuntu/cloudfs/ghost_data/newred_redbook_link_download/downloaded_images/cpu002/downloaded_images,/home/ubuntu/cloudfs/ghost_data/newred_redbook_link_download/downloaded_images/macbookpro13/downloaded_images \
 --draw_img_save_dir=/home/ubuntu/cloudfs/ghost_data/newred_redbook_link_download/downloaded_images/ocr_results \
 --use_mp=True --total_process_num=7 &