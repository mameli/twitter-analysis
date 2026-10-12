# Twitter Analysis

Personal, localhost-only dashboard for tracking how the owner's X (Twitter) audience changes over time, with a focus on who stops following.

## Language

### Relationships

**Follower**:
An account that currently follows the owner.
_Avoid_: Fan, subscriber

**Following**:
An account the owner currently follows.
_Avoid_: Friend, followee

**Mutual**:
An account that is both a Follower and a Following.
_Avoid_: Reciprocal, friend

**One-way following**:
A Following that is not a Follower.
_Avoid_: Non-follower, doesn't-follow-back

**Snapshot**:
The complete set of Followers (or Followings) as observed at one point in time.
_Avoid_: Dump, export

**Sync**:
A manually triggered refresh that takes a new Follower Snapshot and Following Snapshot together and compares them with the previous ones.
_Avoid_: Refresh, poll, fetch

### Changes

**New follow**:
An account absent from one Follower Snapshot and present in the next.
_Avoid_: Gain, new follower event

**Exit**:
An account present in one Snapshot and absent from the next, for any reason.
_Avoid_: Loss, drop

**Unfollow**:
An Exit where the account still exists and is active, so the removal was a deliberate choice.
_Avoid_: Churn

**Follow-churner**:
An account whose Unfollow happens within 14 days of its New follow.
_Avoid_: Follow-for-follow, fake follower
