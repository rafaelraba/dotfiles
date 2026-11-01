function chrome-x --wraps='google-chrome-stable --ozone-platform=x11' --description 'Launch Chrome through XWayland without terminal logs'
    google-chrome-stable --ozone-platform=x11 $argv >/dev/null 2>&1 &
    disown
end
