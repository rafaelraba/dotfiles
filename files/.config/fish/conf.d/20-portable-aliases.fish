# Portable subset translated from Omarchy's Bash defaults, not personal aliases.
# Desktop launchers, automatic agent approvals, and distribution functions omitted.
if not status is-interactive
    return
end

alias .. 'cd ..'
alias ... 'cd ../..'
alias .... 'cd ../../..'
alias g 'git'
alias gcm 'git commit -m'
alias gcam 'git commit -a -m'
alias gcad 'git commit -a --amend'

if type -q eza
    alias ls 'eza -lh --group-directories-first --icons=auto'
    alias lsa 'ls -a'
    alias lt 'eza --tree --level=2 --long --icons --git'
    alias lta 'lt -a'
end
if type -q docker
    alias d 'docker'
end
if type -q rails
    alias r 'rails'
end
if type -q tmux
    function t
        tmux attach; or tmux new -s Work
    end
end
if type -q nvim
    function n
        if test (count $argv) -eq 0
            command nvim .
        else
            command nvim $argv
        end
    end
end
if type -q xdg-open
    function open
        xdg-open $argv >/dev/null 2>&1 &
    end
end
