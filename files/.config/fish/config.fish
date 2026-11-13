if status is-interactive
    # Commands to run in interactive sessions can go here
    if type -q starship
        starship init fish | source
    end

    # The prompt has two lines. When a fresh window (e.g. the Scratch float)
    # resizes right after opening, fish only redraws the last line and the
    # directory line gets duplicated. Clear and repaint on resize, but only
    # while no command has run yet, so real output is never wiped.
    function __mark_command_ran --on-event fish_preexec
        set -g __command_ran 1
        functions -e __mark_command_ran __clear_fresh_on_resize
    end

    function __clear_fresh_on_resize --on-signal WINCH
        set -q __command_ran; and return
        test -n "$(commandline)"; and return
        printf '\e[H\e[2J'
        commandline -f repaint
    end
end
