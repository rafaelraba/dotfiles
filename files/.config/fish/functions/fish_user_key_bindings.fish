function fish_user_key_bindings
    # Ctrl+L: clear the screen. Fish 4's default (scrollback-push) doesn't
    # clear in herdr terminals; this runs clear without typing it.
    bind ctrl-l 'clear -x; commandline -f repaint'
end
