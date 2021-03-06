import os
import random
import shutil
from argparse import ArgumentParser

import torch.backends.cudnn as cudnn
from tensorboardX import SummaryWriter

from trainer import Trainer
import sys, json
from os import path

from utils.tools import get_config, random_bbox, mask_image
from utils.logger import get_logger
from utils.psnr import *
from torchvision.utils import make_grid, save_image

sys.path.append(path.dirname( path.dirname( path.abspath(__file__) ) ))
from data.dataset import VGdataset, vg_collate_fn, test_mask

parser = ArgumentParser()
parser.add_argument('--config', type=str, default='../configs/generative-config.yaml',help="training configuration")
parser.add_argument('--seed', type=int, help='manual seed')
parser.add_argument('--psnr', type=bool)



def main():
    args = parser.parse_args()
    config = get_config(args.config)

    # CUDA configuration
    cuda = config['cuda']
    device_ids = config['gpu_ids']
    if cuda:
        os.environ['CUDA_VISIBLE_DEVICES'] = ','.join(str(i) for i in device_ids)
        device_ids = list(range(len(device_ids)))
        config['gpu_ids'] = device_ids
        cudnn.benchmark = True

    # Configure checkpoint path
    checkpoint_path = os.path.join('checkpoints',
                                   config['dataset_name'])
    if not os.path.exists(checkpoint_path):
        os.makedirs(checkpoint_path)
        os.makedirs(os.path.join(checkpoint_path, 'run'))
        os.makedirs(os.path.join(checkpoint_path, 'log'))
        os.makedirs(os.path.join(checkpoint_path, 'image'))
        os.makedirs(os.path.join(checkpoint_path, 'model'))
    shutil.copy(args.config, os.path.join(checkpoint_path, os.path.basename(args.config)))
    writer = SummaryWriter(logdir=os.path.join(checkpoint_path, 'run'))
    logger = get_logger(os.path.join(checkpoint_path, 'log'))    # get logger and configure it at the first call

    logger.info("Arguments: {}".format(args))
    # Set random seed
    if args.seed is None:
        args.seed = random.randint(1, 10000)
    logger.info("Random seed: {}".format(args.seed))
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    if cuda:
        torch.cuda.manual_seed_all(args.seed)

    # Log the configuration
    logger.info("Configuration: {}".format(config))

    try:  # for unexpected error logging
        # Load the dataset
        logger.info("Training on dataset: {}".format(config['dataset_name']))

        if config['dataset_name'] == "Visual Genome":
            with open(config['vocab_path'], 'r') as f:
                vocab = json.load(f)
            # num_objects = len(vocab['object_idx_to_name'])
        train_dataset = VGdataset(vocab=vocab, h5_path=config['h5_path'],
                                  image_dir=config['image_dir'], image_size=config['image_size'], include_relationships=False)
        loader_kwargs = {
            'batch_size': config['batch_size'],
            'num_workers': config['num_workers'],
            'shuffle': True,
            'collate_fn': vg_collate_fn,
        }
        train_loader = torch.utils.data.DataLoader(dataset=train_dataset, **loader_kwargs)

        # Define the trainer
        trainer = Trainer(config, mode='train')
        logger.info("\n{}".format(trainer.netG))
        logger.info("\n{}".format(trainer.localD))
        logger.info("\n{}".format(trainer.globalD))

        if cuda:
            trainer = nn.parallel.DataParallel(trainer, device_ids=device_ids)
            trainer_module = trainer.module
        else:
            trainer_module = trainer

        # Get the resume iteration to restart training
        start_iteration = trainer_module.resume(config['resume']) if config['resume'] else 1

        iterable_train_loader = iter(train_loader)

        time_count = time.time()

        for iteration in range(start_iteration, config['niter'] + 1):
            try:
                batch = next(iterable_train_loader)
            except (StopIteration, RuntimeError):
                iterable_train_loader = iter(train_loader)
                batch = next(iterable_train_loader)
            if cuda:
                batch = [tensor.cuda() for tensor in batch]

            ## boxes, triples, masks  size: [batch_size, obj_num,..]
            ground_truth, objs, bboxes, triples, masks, obj_to_img, triple_to_img = batch

            x = ground_truth * (1. - masks) # masks: masked pixels 1 otherwise 0
            # testing if image is masked properly
            # test_mask(x[1])
            # assert False

            ###### Forward pass ######
            compute_g_loss = iteration % config['n_critic'] == 0

            try:
                losses, inpainted_result, offset_flow = trainer_module.forward(x, bboxes, masks, ground_truth, compute_g_loss)
            except:
                continue
            # Scalars from different devices are gathered into vectors
            for k in losses.keys():
                if not losses[k].dim() == 0:
                    losses[k] = torch.mean(losses[k])

            ###### Backward pass ######
            # Update D
            trainer_module.optimizer_d.zero_grad()
            losses['d'] = losses['wgan_d'] + losses['wgan_gp'] * config['wgan_gp_lambda']
            losses['d'].backward()


            # Update G
            if compute_g_loss:
                trainer_module.optimizer_g.zero_grad()
                losses['g'] = losses['l1'] * config['l1_loss_alpha'] \
                              + losses['ae'] * config['ae_loss_alpha'] \
                              + losses['wgan_g'] * config['gan_loss_alpha']
                losses['g'].backward()
                trainer_module.optimizer_g.step()
            trainer_module.optimizer_d.step()
            # Log and visualization
            log_losses = ['l1', 'ae', 'wgan_g', 'wgan_d', 'wgan_gp', 'g', 'd']
            if iteration % config['print_iter'] == 0:
                time_count = time.time() - time_count
                speed = config['print_iter'] / time_count
                speed_msg = 'speed: %.2f batches/s ' % speed
                time_count = time.time()

                message = 'Iter: [%d/%d] ' % (iteration, config['niter'])
                for k in log_losses:
                    v = losses.get(k, 0.)
                    writer.add_scalar(k, v, iteration)
                    message += '%s: %.6f ' % (k, v)
                message += speed_msg

                # calculate PSNR
                if args.psnr:
                    # print(ground_truth.size(), inpainted_result.size())
                    psnr_tensor, l2_tensor = psnr(ground_truth, inpainted_result)
                    message += ' psnr: {:.3f}, l2: {:.3f}'.format(psnr_tensor, l2_tensor)

                logger.info(message)

            if iteration % (config['viz_iter']) == 0:
                viz_max_out = config['viz_max_out']
                if x.size(0) > viz_max_out:
                    viz_images = torch.stack([x[:viz_max_out], inpainted_result[:viz_max_out],
                                              offset_flow[:viz_max_out]], dim=1)
                else:
                    viz_images = torch.stack([x, inpainted_result, offset_flow], dim=1)
                viz_images = viz_images.view(-1, *list(x.size())[1:])
                # writer.add_image('valid_img', make_grid(viz_images, nrow=3*4, normalize=True))
                save_image(viz_images,
                                  '%s/niter_%03d.png' % (os.path.join(checkpoint_path,'image'), iteration),
                                  nrow=3 * 4,
                                  normalize=True)

            # Save the model
            if iteration % config['snapshot_save_iter'] == 0:
                trainer_module.save_model(checkpoint_path, iteration)



    except Exception as e:  # for unexpected error logging
        logger.error("{}".format(e))
        raise e


if __name__ == '__main__':
    main()
