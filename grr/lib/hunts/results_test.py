#!/usr/bin/env python
"""Tests for grr.lib.hunts.results."""


from grr.lib import flags
from grr.lib import rdfvalue
from grr.lib import test_lib
from grr.lib.hunts import results as hunts_results
from grr.lib.rdfvalues import flows as rdf_flows


class ResultTest(test_lib.AFF4ObjectTest):

  def testEmptyQueue(self):
    # Create and empty HuntResultCollection.
    collection_urn = rdfvalue.RDFURN("aff4:/testEmptyQueue/collection")
    hunts_results.HuntResultCollection(collection_urn, token=self.token)

    # The queue starts empty, and returns no notifications.
    results = hunts_results.HuntResultQueue.ClaimNotificationsForCollection(
        token=self.token)
    self.assertEqual(None, results[0])
    self.assertEqual([], results[1])

  def testNotificationsContainTimestamps(self):
    collection_urn = rdfvalue.RDFURN(
        "aff4:/testNotificationsContainTimestamps/collection")
    for i in range(5):
      hunts_results.HuntResultCollection.StaticAdd(
          collection_urn, self.token, rdf_flows.GrrMessage(request_id=i))

    # If we claim results, we should get all 5.
    results = hunts_results.HuntResultQueue.ClaimNotificationsForCollection(
        token=self.token)
    self.assertEqual(collection_urn, results[0])
    self.assertEqual(5, len(results[1]))

    # Read all the results, using the contained (ts, suffix) pairs.
    values_read = []
    collection = hunts_results.HuntResultCollection(
        collection_urn, token=self.token)
    for message in collection.MultiResolve([(ts, suffix)
                                            for (_, ts, suffix) in results[1]]):
      values_read.append(message.request_id)
    self.assertEqual(sorted(values_read), range(5))

  def testNotificationClaimsTimeout(self):
    collection_urn = rdfvalue.RDFURN(
        "aff4:/testNotificationClaimsTimeout/collection")
    for i in range(5):
      hunts_results.HuntResultCollection.StaticAdd(
          collection_urn, self.token, rdf_flows.GrrMessage(request_id=i))

    results_1 = hunts_results.HuntResultQueue.ClaimNotificationsForCollection(
        token=self.token)
    self.assertEqual(5, len(results_1[1]))

    # Check that we have a claim - that another read returns nothing.
    results_2 = hunts_results.HuntResultQueue.ClaimNotificationsForCollection(
        token=self.token)
    self.assertEqual(0, len(results_2[1]))

    # Push time forward past the default claim timeout, then we should be able
    # to re-read (and re-claim).
    with test_lib.FakeTime(rdfvalue.RDFDatetime.Now() + rdfvalue.Duration(
        "45m")):
      results_3 = hunts_results.HuntResultQueue.ClaimNotificationsForCollection(
          token=self.token)
    self.assertEqual(results_3, results_1)

  def testDelete(self):
    collection_urn = rdfvalue.RDFURN("aff4:/testDelete/collection")
    for i in range(5):
      hunts_results.HuntResultCollection.StaticAdd(
          collection_urn, self.token, rdf_flows.GrrMessage(request_id=i))

    results_1 = hunts_results.HuntResultQueue.ClaimNotificationsForCollection(
        token=self.token)
    self.assertEqual(5, len(results_1[1]))

    hunts_results.HuntResultQueue.DeleteNotifications(
        [record_id for (record_id, _, _) in results_1[1]], token=self.token)

    # Push time forward past the default claim timeout, then we should still
    # read nothing.
    with test_lib.FakeTime(rdfvalue.RDFDatetime.Now() + rdfvalue.Duration(
        "45m")):
      results_2 = hunts_results.HuntResultQueue.ClaimNotificationsForCollection(
          token=self.token)
    self.assertEqual(0, len(results_2[1]))

  def testNotificationsSplitByCollection(self):
    # Create two HuntResultCollections.
    collection_urn_1 = rdfvalue.RDFURN(
        "aff4:/testNotificationsSplitByCollection/collection_1")
    collection_urn_2 = rdfvalue.RDFURN(
        "aff4:/testNotificationsSplitByCollection/collection_2")

    # Add 100 records to each collection, in an interleaved manner.
    for i in range(100):
      hunts_results.HuntResultCollection.StaticAdd(
          collection_urn_1, self.token, rdf_flows.GrrMessage(request_id=i))
      hunts_results.HuntResultCollection.StaticAdd(
          collection_urn_2,
          self.token,
          rdf_flows.GrrMessage(request_id=100 + i))

    # The first result was added to collection 1, so this should return
    # all 100 results for collection 1.
    results_1 = hunts_results.HuntResultQueue.ClaimNotificationsForCollection(
        token=self.token)
    self.assertEqual(collection_urn_1, results_1[0])
    self.assertEqual(100, len(results_1[1]))

    # The first call claimed all the notifications for collection 1. These are
    # claimed, so another call should skip them and give all notifications for
    # collection 2.
    results_2 = hunts_results.HuntResultQueue.ClaimNotificationsForCollection(
        token=self.token)
    self.assertEqual(collection_urn_2, results_2[0])
    self.assertEqual(100, len(results_2[1]))

    values_read = []
    collection_2 = hunts_results.HuntResultCollection(
        collection_urn_2, token=self.token)
    for message in collection_2.MultiResolve([(
        ts, suffix) for (_, ts, suffix) in results_2[1]]):
      values_read.append(message.request_id)
    self.assertEqual(sorted(values_read), range(100, 200))


def main(argv):
  test_lib.main(argv)


if __name__ == "__main__":
  flags.StartMain(main)
