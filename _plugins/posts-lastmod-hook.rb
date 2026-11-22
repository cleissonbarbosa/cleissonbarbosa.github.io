#!/usr/bin/env ruby
#
# Check for changed posts
#
# A post counts as updated when a commit after the one that created it changed
# something a reader would notice. Commits that only touch the front matter
# keys in IGNORED_KEYS (narration, pinning, language) don't count, so a bulk
# metadata edit doesn't mark every post as updated.

require 'open3'

module PostsLastmod
  IGNORED_KEYS = %w[audio pin lang].freeze
  IGNORED_LINE = /\A[+-](?:#{IGNORED_KEYS.join('|')}):/.freeze

  module_function

  # ISO date of the last meaningful change to the post, or nil if there is none.
  def lastmod(path)
    # Run from the post's directory so git finds the repo wherever Jekyll was started.
    log, status = Open3.capture2(
      'git', 'log', '--format=%x01%ad', '--date=iso', '-p', '--unified=0', '--no-color', '--', path,
      chdir: File.dirname(path)
    )
    return nil unless status.success?

    commits = log.force_encoding('UTF-8').scrub.split("\x01").drop(1)
    # The oldest commit created the post, so it is never an update.
    commits[0...-1].each do |commit|
      date, patch = commit.split("\n", 2)
      return date.strip if meaningful?(patch.to_s)
    end
    nil
  end

  def meaningful?(patch)
    in_hunk = false
    patch.each_line.any? do |line|
      in_hunk = true if line.start_with?('@@')
      in_hunk && line.match?(/\A[+-]/) && !line.match?(IGNORED_LINE)
    end
  end
end

Jekyll::Hooks.register :posts, :post_init do |post|
  lastmod_date = PostsLastmod.lastmod(post.path)
  post.data['last_modified_at'] = lastmod_date if lastmod_date
end
