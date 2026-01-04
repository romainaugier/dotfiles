#!/bin/bash

# Just make links to current dotfiles

# vim

if [ -e ~/.vimrc ]; then
    rm ~/.vimrc
fi

ln .vimrc ~/.vimrc

# tmux

if [ -e ~/.tmux.conf ]; then
    rm ~/.tmux.conf
fi

ln .tmux.conf ~/.tmux.conf

# zsh

if [ -e ~/.zshrc ]; then
    rm ~/.zshrc
fi

ln .zshrc ~/.zshrc

# zed

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

# gdb

if [ -e ~/.gdbui.py ]; then
    rm ~/.gdbui.py
fi

ln .gdbui.py ~/.gdbui.py

if [ -e ~/.gdbinit ]; then
    rm ~/.gdbinit
fi

ln .gdbinit ~/.gdbinit
