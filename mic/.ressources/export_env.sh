# !/bin/bash

BASHRC="$HOME/.bashrc"

ARG=$1
echo "path to append to PATH environement variable: $ARG "
export_string='export PATH=$PATH:'
query="$export_string$ARG"
test=$( grep "$query" $BASHRC )
if [ -n "$test" ]
then
    echo "$ARG already exists in PATH"
else
    echo "$query" >> $BASHRC
    echo "$ARG added to PATH "
fi
wait
source $BASHRC
