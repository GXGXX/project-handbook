# README 演示视频

`docs/media/project-handbook-demo.mp4`（约 1 分钟，1920×1080，无声）用的是 `docs/examples/checkin.flow.json` 生成的真实网页，由脚本操作录制，不是手工剪辑。页面改版后可以重录：

```bash
# 在仓库根目录；需要 Node + Playwright、Python 3、ffmpeg
node docs/video/director.cjs demo-video

cd demo-video
for s in $(cat frames/scenes.txt); do
  ffmpeg -v error -y -framerate 30 -i frames/$s/%05d.jpg -c:v libx264 -crf 20 -preset veryfast -pix_fmt yuv420p -r 30 $s.mp4
done
for s in $(cat frames/scenes.txt); do echo "file '$PWD/$s.mp4'"; done > list.txt
ffmpeg -v error -y -f concat -safe 0 -i list.txt -c copy -movflags +faststart project-handbook-demo.mp4

# README 里自动播放的动图：GitHub 网页不能直接播放仓库里的 mp4，所以 README 用 GIF 展示
ffmpeg -v error -y -i project-handbook-demo.mp4 -vf "fps=10,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=none:diff_mode=rectangle" demo.gif
```

生成后把 `project-handbook-demo.mp4` 放到 `docs/media/`，`demo.gif` 放到 `docs/images/`。

- `stage.html`：画面外框，包括标题页、一个通用的「AI 对话」窗口（不模仿任何具体产品）、字幕和鼠标。
- `director.cjs`：每一幕的操作、字幕和时长。只想重拍某几幕时，在输出目录后面加上幕名，例如 `node docs/video/director.cjs demo-video 03-step,04-question`。
