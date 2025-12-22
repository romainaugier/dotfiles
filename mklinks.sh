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
