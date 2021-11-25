MODEL=$1

if [ $MODEL == "generative-attention" ]; then
    cd generative-inpainting
    python test.py --config '../configs/generative-config.yaml'

if [ $MODEL == "edge-connect" ]; then
    cd edge-connect
    python test.py \
  --checkpoints ./checkpoints/places2
  --input ./examples/places2/images
  --mask ./examples/places2/masks
  --output ./checkpoints/results

else
    echo "Available arguments are [generative-attention]"
    exit 1
fi