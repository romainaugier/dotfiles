#!/bin/bash

# Just make links to current dotfiles

if [ -e ~/.vimrc ]; then
    rm ~/.vimrc
fi

ln .vimrc ~/.vimrc

if [ -e ~/.tmux.conf ]; then
    rm ~/.tmux.conf
fi

ln .tmux.conf ~/.tmux.conf

if [ -e ~/.zshrc ]; then
    rm ~/.zshrc
fi

ln .zshrc ~/.zshrc

if [ -e ~/.config/zed/settings.json ]; then
    rm ~/.config/zed/settings.json 
else
    mkdir -p ~/.config/zed/
fi

ln zed_settings.json ~/.config/zed/settings.json 

if [ -e ~/.config/zed/keymap.json ]; then
    rm ~/.config/zed/keymap.json 
fi

ln zed_keymap.json ~/.config/zed/keymap.json 
