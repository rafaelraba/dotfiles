return {
  {
    "iamcco/markdown-preview.nvim",
    init = function()
      vim.g.mkdp_markdown_css = vim.fn.expand("~/.config/nvim/markdown-preview.css")
      vim.g.mkdp_theme = "light"
    end,
  },
}
