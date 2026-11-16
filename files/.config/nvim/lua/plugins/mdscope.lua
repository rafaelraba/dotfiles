return {
  {
    dir = vim.fn.expand("~/Code/mdscope.nvim"),
    name = "mdscope.nvim",
    ft = "markdown",
    keys = {
      { "<leader>mS", "<cmd>MdscopeStart<cr>", ft = "markdown", desc = "Start Markdown preview (mdscope)" },
      { "<leader>mX", "<cmd>MdscopeStop<cr>", ft = "markdown", desc = "Stop Markdown preview (mdscope)" },
    },
  },
}
