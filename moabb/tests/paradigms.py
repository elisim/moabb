import logging
import unittest

import numpy as np
from mne import BaseEpochs
from mne.io import BaseRaw

from moabb.datasets.fake import FakeDataset
from moabb.paradigms import (
    P300,
    SSVEP,
    BaseMotorImagery,
    BaseP300,
    BaseSSVEP,
    FilterBankLeftRightImagery,
    FilterBankMotorImagery,
    FilterBankSSVEP,
    LeftRightImagery,
    RestingStateToP300Adapter,
)


log = logging.getLogger(__name__)
log.setLevel(logging.ERROR)


class SimpleMotorImagery(BaseMotorImagery):  # Needed to assess BaseImagery
    def used_events(self, dataset):
        return dataset.event_id


class Test_MotorImagery(unittest.TestCase):
    def test_BaseImagery_paradigm(self):
        paradigm = SimpleMotorImagery()
        dataset = FakeDataset(paradigm="imagery")
        X, labels, metadata = paradigm.get_data(dataset, subjects=[1])

        # we should have all the same length
        self.assertEqual(len(X), len(labels), len(metadata))
        # X must be a 3D Array
        self.assertEqual(len(X.shape), 3)
        # labels must contain 3 values
        self.assertEqual(len(np.unique(labels)), 3)
        # metadata must have subjets, sessions, runs
        self.assertTrue("subject" in metadata.columns)
        self.assertTrue("session" in metadata.columns)
        self.assertTrue("run" in metadata.columns)
        # we should have only one subject in the metadata
        self.assertEqual(np.unique(metadata.subject), 1)
        # we should have two sessions in the metadata
        self.assertEqual(len(np.unique(metadata.session)), 2)
        # should return epochs
        epochs, _, _ = paradigm.get_data(dataset, subjects=[1], return_epochs=True)
        self.assertIsInstance(epochs, BaseEpochs)
        # should return raws
        raws, _, _ = paradigm.get_data(dataset, subjects=[1], return_raws=True)
        for raw in raws:
            self.assertIsInstance(raw, BaseRaw)
        # should raise error
        self.assertRaises(
            ValueError,
            paradigm.get_data,
            dataset,
            subjects=[1],
            return_epochs=True,
            return_raws=True,
        )

    def test_BaseImagery_channel_order(self):
        """test if paradigm return correct channel order, see issue #227"""
        datasetA = FakeDataset(paradigm="imagery", channels=["C3", "Cz", "C4"])
        datasetB = FakeDataset(paradigm="imagery", channels=["Cz", "C4", "C3"])
        paradigm = SimpleMotorImagery(channels=["C4", "C3", "Cz"])

        ep1, _, _ = paradigm.get_data(datasetA, subjects=[1], return_epochs=True)
        ep2, _, _ = paradigm.get_data(datasetB, subjects=[1], return_epochs=True)
        self.assertEqual(ep1.info["ch_names"], ep2.info["ch_names"])

    def test_BaseImagery_tmintmax(self):
        self.assertRaises(ValueError, SimpleMotorImagery, tmin=1, tmax=0)

    def test_BaseImagery_filters(self):
        # can work with filter bank
        paradigm = SimpleMotorImagery(filters=[[7, 12], [12, 24]])
        dataset = FakeDataset(paradigm="imagery")
        X, labels, metadata = paradigm.get_data(dataset, subjects=[1])

        # X must be a 4D Array
        self.assertEqual(len(X.shape), 4)
        self.assertEqual(X.shape[-1], 2)
        # should return epochs
        epochs, _, _ = paradigm.get_data(dataset, subjects=[1], return_epochs=True)
        self.assertIsInstance(epochs, BaseEpochs)

    def test_baseImagery_wrongevent(self):
        # test process_raw return empty list if raw does not contain any
        # selected event. cetain runs in dataset are event specific.
        paradigm = SimpleMotorImagery(filters=[[7, 12], [12, 24]])
        dataset = FakeDataset(paradigm="imagery")
        raw = dataset.get_data([1])[1]["session_0"]["run_0"]
        # add something on the event channel
        raw._data[-1] *= 10
        self.assertIsNone(paradigm.process_raw(raw, dataset))
        # zeros it out
        raw._data[-1] *= 0
        self.assertIsNone(paradigm.process_raw(raw, dataset))

    def test_BaseImagery_noevent(self):
        # Assert error if events from paradigm and dataset dont overlap
        paradigm = SimpleMotorImagery(events=["left_hand", "right_hand"])
        dataset = FakeDataset(paradigm="imagery")
        self.assertRaises(AssertionError, paradigm.get_data, dataset)

    def test_BaseImagery_droppedevent(self):
        dataset = FakeDataset(paradigm="imagery")
        tmax = dataset.interval[1]
        # with regular windows, all epochs should be valid:
        paradigm1 = SimpleMotorImagery(tmax=tmax)
        # with large windows, some epochs will have to be dropped:
        paradigm2 = SimpleMotorImagery(tmax=10 * tmax)
        # with epochs:
        epochs1, labels1, metadata1 = paradigm1.get_data(dataset, return_epochs=True)
        epochs2, labels2, metadata2 = paradigm2.get_data(dataset, return_epochs=True)
        self.assertEqual(len(epochs1), len(labels1), len(metadata1))
        self.assertEqual(len(epochs2), len(labels2), len(metadata2))
        self.assertGreater(len(epochs1), len(epochs2))
        # with np.array:
        X1, labels1, metadata1 = paradigm1.get_data(dataset)
        X2, labels2, metadata2 = paradigm2.get_data(dataset)
        self.assertEqual(len(X1), len(labels1), len(metadata1))
        self.assertEqual(len(X2), len(labels2), len(metadata2))
        self.assertGreater(len(X1), len(X2))

    def test_BaseImagery_epochsmetadata(self):
        dataset = FakeDataset(paradigm="imagery")
        paradigm = SimpleMotorImagery()
        epochs, _, metadata = paradigm.get_data(dataset, return_epochs=True)
        # does not work with multiple filters:
        self.assertTrue(metadata.equals(epochs.metadata))

    def test_LeftRightImagery_paradigm(self):
        # with a good dataset
        paradigm = LeftRightImagery()
        dataset = FakeDataset(event_list=["left_hand", "right_hand"], paradigm="imagery")
        X, labels, metadata = paradigm.get_data(dataset, subjects=[1])

        self.assertEqual(len(np.unique(labels)), 2)
        self.assertEqual(list(np.unique(labels)), ["left_hand", "right_hand"])
        # should return epochs
        epochs, _, _ = paradigm.get_data(dataset, subjects=[1], return_epochs=True)
        self.assertIsInstance(epochs, BaseEpochs)

    def test_LeftRightImagery_noevent(self):
        # we cant pass event to this class
        self.assertRaises(ValueError, LeftRightImagery, events=["a"])

    def test_LeftRightImagery_badevents(self):
        paradigm = LeftRightImagery()
        # does not accept dataset with bad event
        dataset = FakeDataset(paradigm="imagery")
        self.assertRaises(AssertionError, paradigm.get_data, dataset)

    def test_FilterBankMotorImagery_paradigm(self):
        # can work with filter bank
        paradigm = FilterBankMotorImagery()
        dataset = FakeDataset(paradigm="imagery")
        X, labels, metadata = paradigm.get_data(dataset, subjects=[1])

        # X must be a 4D Array
        self.assertEqual(len(X.shape), 4)
        self.assertEqual(X.shape[-1], 6)
        # should return epochs
        epochs, _, _ = paradigm.get_data(dataset, subjects=[1], return_epochs=True)
        self.assertIsInstance(epochs, BaseEpochs)

    def test_FilterBankMotorImagery_moreclassesthanevent(self):
        self.assertRaises(
            AssertionError, FilterBankMotorImagery, n_classes=3, events=["hands", "feet"]
        )

    def test_FilterBankLeftRightImagery_paradigm(self):
        # can work with filter bank
        paradigm = FilterBankLeftRightImagery()
        dataset = FakeDataset(event_list=["left_hand", "right_hand"], paradigm="imagery")
        X, labels, metadata = paradigm.get_data(dataset, subjects=[1])

        # X must be a 4D Array
        self.assertEqual(len(X.shape), 4)
        self.assertEqual(X.shape[-1], 6)
        # should return epochs
        epochs, _, _ = paradigm.get_data(dataset, subjects=[1], return_epochs=True)
        self.assertIsInstance(epochs, BaseEpochs)


class SimpleP300(BaseP300):  # Needed to assess BaseP300
    def used_events(self, dataset):
        return dataset.event_id


class Test_P300(unittest.TestCase):
    def test_BaseP300_paradigm(self):
        paradigm = SimpleP300()
        dataset = FakeDataset(paradigm="p300", event_list=["Target", "NonTarget"])
        X, labels, metadata = paradigm.get_data(dataset, subjects=[1])

        # we should have all the same length
        self.assertEqual(len(X), len(labels), len(metadata))
        # X must be a 3D Array
        self.assertEqual(len(X.shape), 3)
        # labels must contain 2 values (Target/NonTarget)
        self.assertEqual(len(np.unique(labels)), 2)
        # metadata must have subjets, sessions, runs
        self.assertTrue("subject" in metadata.columns)
        self.assertTrue("session" in metadata.columns)
        self.assertTrue("run" in metadata.columns)
        # we should have only one subject in the metadata
        self.assertEqual(np.unique(metadata.subject), 1)
        # we should have two sessions in the metadata
        self.assertEqual(len(np.unique(metadata.session)), 2)
        # should return epochs
        epochs, _, _ = paradigm.get_data(dataset, subjects=[1], return_epochs=True)
        self.assertIsInstance(epochs, BaseEpochs)
        # should return raws
        raws, _, _ = paradigm.get_data(dataset, subjects=[1], return_raws=True)
        for raw in raws:
            self.assertIsInstance(raw, BaseRaw)
        # should raise error
        self.assertRaises(
            ValueError,
            paradigm.get_data,
            dataset,
            subjects=[1],
            return_epochs=True,
            return_raws=True,
        )

    def test_BaseP300_channel_order(self):
        """test if paradigm return correct channel order, see issue #227"""
        datasetA = FakeDataset(
            paradigm="p300",
            channels=["C3", "Cz", "C4"],
            event_list=["Target", "NonTarget"],
        )
        datasetB = FakeDataset(
            paradigm="p300",
            channels=["Cz", "C4", "C3"],
            event_list=["Target", "NonTarget"],
        )
        paradigm = SimpleP300(channels=["C4", "C3", "Cz"])

        ep1, _, _ = paradigm.get_data(datasetA, subjects=[1], return_epochs=True)
        ep2, _, _ = paradigm.get_data(datasetB, subjects=[1], return_epochs=True)
        self.assertEqual(ep1.info["ch_names"], ep2.info["ch_names"])

    def test_BaseP300_tmintmax(self):
        self.assertRaises(ValueError, SimpleP300, tmin=1, tmax=0)

    def test_BaseP300_filters(self):
        # can work with filter bank
        paradigm = SimpleP300(filters=[[1, 12], [12, 24]])
        dataset = FakeDataset(paradigm="p300", event_list=["Target", "NonTarget"])
        X, labels, metadata = paradigm.get_data(dataset, subjects=[1])

        # X must be a 4D Array
        self.assertEqual(len(X.shape), 4)
        self.assertEqual(X.shape[-1], 2)
        # should return epochs
        epochs, _, _ = paradigm.get_data(dataset, subjects=[1], return_epochs=True)
        self.assertIsInstance(epochs, BaseEpochs)

    def test_BaseP300_wrongevent(self):
        # test process_raw return empty list if raw does not contain any
        # selected event. cetain runs in dataset are event specific.
        paradigm = SimpleP300(filters=[[1, 12], [12, 24]])
        dataset = FakeDataset(paradigm="p300", event_list=["Target", "NonTarget"])
        raw = dataset.get_data([1])[1]["session_0"]["run_0"]
        # add something on the event channel
        raw._data[-1] *= 10
        self.assertIsNone(paradigm.process_raw(raw, dataset))
        # zeros it out
        raw._data[-1] *= 0
        self.assertIsNone(paradigm.process_raw(raw, dataset))

    def test_BaseP300_droppedevent(self):
        dataset = FakeDataset(paradigm="p300", event_list=["Target", "NonTarget"])
        tmax = dataset.interval[1]
        # with regular windows, all epochs should be valid:
        paradigm1 = SimpleP300(tmax=tmax)
        # with large windows, some epochs will have to be dropped:
        paradigm2 = SimpleP300(tmax=10 * tmax)
        # with epochs:
        epochs1, labels1, metadata1 = paradigm1.get_data(dataset, return_epochs=True)
        epochs2, labels2, metadata2 = paradigm2.get_data(dataset, return_epochs=True)
        self.assertEqual(len(epochs1), len(labels1), len(metadata1))
        self.assertEqual(len(epochs2), len(labels2), len(metadata2))
        self.assertGreater(len(epochs1), len(epochs2))
        # with np.array:
        X1, labels1, metadata1 = paradigm1.get_data(dataset)
        X2, labels2, metadata2 = paradigm2.get_data(dataset)
        self.assertEqual(len(X1), len(labels1), len(metadata1))
        self.assertEqual(len(X2), len(labels2), len(metadata2))
        self.assertGreater(len(X1), len(X2))

    def test_BaseP300_epochsmetadata(self):
        dataset = FakeDataset(paradigm="p300", event_list=["Target", "NonTarget"])
        paradigm = SimpleP300()
        epochs, _, metadata = paradigm.get_data(dataset, return_epochs=True)
        # does not work with multiple filters:
        self.assertTrue(metadata.equals(epochs.metadata))

    def test_P300_specifyevent(self):
        # we cant pass event to this class
        self.assertRaises(ValueError, P300, events=["a"])

    def test_P300_wrongevent(self):
        # does not accept dataset with bad event
        paradigm = P300()
        dataset = FakeDataset(paradigm="p300")
        self.assertRaises(AssertionError, paradigm.get_data, dataset)

    def test_P300_paradigm(self):
        # with a good dataset
        paradigm = P300()
        dataset = FakeDataset(event_list=["Target", "NonTarget"], paradigm="p300")
        X, labels, metadata = paradigm.get_data(dataset, subjects=[1])
        self.assertEqual(len(np.unique(labels)), 2)
        self.assertEqual(list(np.unique(labels)), sorted(["Target", "NonTarget"]))
        # should return epochs
        epochs, _, _ = paradigm.get_data(dataset, subjects=[1], return_epochs=True)
        self.assertIsInstance(epochs, BaseEpochs)


class Test_RestingState(unittest.TestCase):
    def test_RestingState_paradigm(self):
        event_list = ["Open", "Close"]
        paradigm = RestingStateToP300Adapter(events=event_list)
        dataset = FakeDataset(paradigm="rstate", event_list=event_list)
        X, labels, metadata = paradigm.get_data(dataset, subjects=[1])

        # we should have all the same length
        self.assertEqual(len(X), len(labels), len(metadata))
        # X must be a 3D Array
        self.assertEqual(len(X.shape), 3)
        # labels must contain 2 values (Open/Close)
        self.assertEqual(len(np.unique(labels)), 2)
        # metadata must have subjets, sessions, runs
        self.assertTrue("subject" in metadata.columns)
        self.assertTrue("session" in metadata.columns)
        self.assertTrue("run" in metadata.columns)
        # we should have only one subject in the metadata
        self.assertEqual(np.unique(metadata.subject), 1)
        # we should have two sessions in the metadata
        self.assertEqual(len(np.unique(metadata.session)), 2)
        # should return epochs
        epochs, _, _ = paradigm.get_data(dataset, subjects=[1], return_epochs=True)
        self.assertIsInstance(epochs, BaseEpochs)
        # should return raws
        raws, _, _ = paradigm.get_data(dataset, subjects=[1], return_raws=True)
        for raw in raws:
            self.assertIsInstance(raw, BaseRaw)
        # should raise error
        self.assertRaises(
            ValueError,
            paradigm.get_data,
            dataset,
            subjects=[1],
            return_epochs=True,
            return_raws=True,
        )

    def test_RestingState_default_values(self):
        paradigm = RestingStateToP300Adapter()
        assert paradigm.tmin == 10
        assert paradigm.tmax == 50
        assert paradigm.fmin == 1
        assert paradigm.fmax == 35
        assert paradigm.resample == 128


class Test_SSVEP(unittest.TestCase):
    def test_BaseSSVEP_paradigm(self):
        paradigm = BaseSSVEP(n_classes=None)
        dataset = FakeDataset(paradigm="ssvep")
        X, labels, metadata = paradigm.get_data(dataset, subjects=[1])

        # Verify that they have the same length
        self.assertEqual(len(X), len(labels), len(metadata))
        # X must be a 3D array
        self.assertEqual(len(X.shape), 3)
        # labels must contain 3 values
        self.assertEqual(len(np.unique(labels)), 3)
        # metadata must have subjets, sessions, runs
        self.assertTrue("subject" in metadata.columns)
        self.assertTrue("session" in metadata.columns)
        self.assertTrue("run" in metadata.columns)
        # Only one subject in the metadata
        self.assertEqual(np.unique(metadata.subject), 1)
        # we should have two sessions in the metadata, n_classes = 2 as default
        self.assertEqual(len(np.unique(metadata.session)), 2)
        # should return epochs
        epochs, _, _ = paradigm.get_data(dataset, subjects=[1], return_epochs=True)
        self.assertIsInstance(epochs, BaseEpochs)
        # should return raws
        raws, _, _ = paradigm.get_data(dataset, subjects=[1], return_raws=True)
        for raw in raws:
            self.assertIsInstance(raw, BaseRaw)
        # should raise error
        self.assertRaises(
            ValueError,
            paradigm.get_data,
            dataset,
            subjects=[1],
            return_epochs=True,
            return_raws=True,
        )

    def test_BaseSSVEP_channel_order(self):
        """test if paradigm return correct channel order, see issue #227"""
        datasetA = FakeDataset(paradigm="ssvep", channels=["C3", "Cz", "C4"])
        datasetB = FakeDataset(paradigm="ssvep", channels=["Cz", "C4", "C3"])
        paradigm = BaseSSVEP(channels=["C4", "C3", "Cz"])

        ep1, _, _ = paradigm.get_data(datasetA, subjects=[1], return_epochs=True)
        ep2, _, _ = paradigm.get_data(datasetB, subjects=[1], return_epochs=True)
        self.assertEqual(ep1.info["ch_names"], ep2.info["ch_names"])

    def test_baseSSVEP_tmintmax(self):
        # Verify that tmin < tmax
        self.assertRaises(ValueError, BaseSSVEP, tmin=1, tmax=0)

    def test_BaseSSVEP_filters(self):
        # Accept filters
        paradigm = BaseSSVEP(filters=[(10.5, 11.5), (12.5, 13.5)])
        dataset = FakeDataset(paradigm="ssvep")
        X, labels, metadata = paradigm.get_data(dataset, subjects=[1])

        # X must be a 4D array
        self.assertEqual(len(X.shape), 4)
        # Last dim should be 2 as the number of filters
        self.assertEqual(X.shape[-1], 2)
        # should return epochs
        epochs, _, _ = paradigm.get_data(dataset, subjects=[1], return_epochs=True)
        self.assertIsInstance(epochs, BaseEpochs)

    def test_BaseSSVEP_nclasses_default(self):
        # Default is with 3 classes
        paradigm = BaseSSVEP()
        dataset = FakeDataset(paradigm="ssvep")
        X, labels, metadata = paradigm.get_data(dataset, subjects=[1])

        # labels must contain all 3 classes of dataset,
        # as n_classes is "None" by default (taking all classes)
        self.assertEqual(len(np.unique(labels)), 3)

    def test_BaseSSVEP_specified_nclasses(self):
        # Set the number of classes
        paradigm = BaseSSVEP(n_classes=3)
        dataset = FakeDataset(event_list=["13", "15", "17", "19"], paradigm="ssvep")
        X, labels, metadata = paradigm.get_data(dataset, subjects=[1])

        # labels must contain 3 values
        self.assertEqual(len(np.unique(labels)), 3)

    def test_BaseSSVEP_toomany_nclasses(self):
        paradigm = BaseSSVEP(n_classes=4)
        dataset = FakeDataset(event_list=["13", "15"], paradigm="ssvep")
        self.assertRaises(ValueError, paradigm.get_data, dataset)

    def test_BaseSSVEP_moreclassesthanevent(self):
        self.assertRaises(AssertionError, BaseSSVEP, n_classes=3, events=["13.", "14."])

    def test_BaseSSVEP_droppedevent(self):
        dataset = FakeDataset(paradigm="ssvep")
        tmax = dataset.interval[1]
        # with regular windows, all epochs should be valid:
        paradigm1 = BaseSSVEP(tmax=tmax)
        # with large windows, some epochs will have to be dropped:
        paradigm2 = BaseSSVEP(tmax=10 * tmax)
        # with epochs:
        epochs1, labels1, metadata1 = paradigm1.get_data(dataset, return_epochs=True)
        epochs2, labels2, metadata2 = paradigm2.get_data(dataset, return_epochs=True)
        self.assertEqual(len(epochs1), len(labels1), len(metadata1))
        self.assertEqual(len(epochs2), len(labels2), len(metadata2))
        self.assertGreater(len(epochs1), len(epochs2))
        # with np.array:
        X1, labels1, metadata1 = paradigm1.get_data(dataset)
        X2, labels2, metadata2 = paradigm2.get_data(dataset)
        self.assertEqual(len(X1), len(labels1), len(metadata1))
        self.assertEqual(len(X2), len(labels2), len(metadata2))
        self.assertGreater(len(X1), len(X2))

    def test_BaseSSVEP_epochsmetadata(self):
        dataset = FakeDataset(paradigm="ssvep")
        paradigm = BaseSSVEP()
        epochs, _, metadata = paradigm.get_data(dataset, return_epochs=True)
        # does not work with multiple filters:
        self.assertTrue(metadata.equals(epochs.metadata))

    def test_SSVEP_noevent(self):
        # Assert error if events from paradigm and dataset dont overlap
        paradigm = SSVEP(events=["11", "12"], n_classes=2)
        dataset = FakeDataset(event_list=["13", "14"], paradigm="ssvep")
        self.assertRaises(AssertionError, paradigm.get_data, dataset)

    def test_SSVEP_paradigm(self):
        paradigm = SSVEP(n_classes=None)
        dataset = FakeDataset(event_list=["13", "15", "17", "19"], paradigm="ssvep")
        X, labels, metadata = paradigm.get_data(dataset, subjects=[1])

        # Verify that they have the same length
        self.assertEqual(len(X), len(labels), len(metadata))
        # X must be a 3D array
        self.assertEqual(len(X.shape), 3)
        # labels must contain 4 values, defined in the dataset
        self.assertEqual(len(np.unique(labels)), 4)
        # metadata must have subjets, sessions, runs
        self.assertTrue("subject" in metadata.columns)
        self.assertTrue("session" in metadata.columns)
        self.assertTrue("run" in metadata.columns)
        # Only one subject in the metadata
        self.assertEqual(np.unique(metadata.subject), 1)
        # We should have two sessions in the metadata
        self.assertEqual(len(np.unique(metadata.session)), 2)
        # should return epochs
        epochs, _, _ = paradigm.get_data(dataset, subjects=[1], return_epochs=True)
        self.assertIsInstance(epochs, BaseEpochs)

    def test_SSVEP_singlepass(self):
        # Accept only single pass filter
        paradigm = SSVEP(fmin=2, fmax=25)
        dataset = FakeDataset(paradigm="ssvep")
        X, labels, metadata = paradigm.get_data(dataset, subjects=[1])

        # Verify that they have the same length
        self.assertEqual(len(X), len(labels), len(metadata))
        # X must be a 3D array
        self.assertEqual(len(X.shape), 3)
        # labels must contain all 3 classes of dataset,
        # as n_classes is "None" by default (taking all classes)
        self.assertEqual(len(np.unique(labels)), 3)
        # should return epochs
        epochs, _, _ = paradigm.get_data(dataset, subjects=[1], return_epochs=True)
        self.assertIsInstance(epochs, BaseEpochs)

    def test_SSVEP_filter(self):
        # Do not accept multiple filters
        self.assertRaises(ValueError, SSVEP, filters=[(10.5, 11.5), (12.5, 13.5)])

    def test_FilterBankSSVEP_paradigm(self):
        # FilterBankSSVEP with all events
        paradigm = FilterBankSSVEP(n_classes=None)
        dataset = FakeDataset(event_list=["13", "15", "17", "19"], paradigm="ssvep")
        X, labels, metadata = paradigm.get_data(dataset, subjects=[1])

        # X must be a 4D array
        self.assertEqual(len(X.shape), 4)
        # X must be a 4D array with d=4 as last dimension for the 4 events
        self.assertEqual(X.shape[-1], 4)
        # should return epochs
        epochs, _, _ = paradigm.get_data(dataset, subjects=[1], return_epochs=True)
        self.assertIsInstance(epochs, BaseEpochs)

    def test_FilterBankSSVEP_filters(self):
        # can work with filter bank
        paradigm = FilterBankSSVEP(filters=[(10.5, 11.5), (12.5, 13.5)])
        dataset = FakeDataset(event_list=["13", "15", "17"], paradigm="ssvep")
        X, labels, metadata = paradigm.get_data(dataset, subjects=[1])

        # X must be a 4D array with d=2 as last dimension for the 2 filters
        self.assertEqual(len(X.shape), 4)
        self.assertEqual(X.shape[-1], 2)
        # should return epochs
        epochs, _, _ = paradigm.get_data(dataset, subjects=[1], return_epochs=True)
        self.assertIsInstance(epochs, BaseEpochs)
