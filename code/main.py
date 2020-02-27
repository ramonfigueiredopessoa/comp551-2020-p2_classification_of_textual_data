'''
####################################
# Classification of text documents
####################################

This code uses many machine learning approaches to classify documents by topics using a bag-of-words approach.

The datasets used in this are the 20 newsgroups dataset (https://scikit-learn.org/stable/modules/generated/sklearn.datasets.fetch_20newsgroups.html) and the IMDB Reviews dataset (http://ai.stanford.edu/~amaas/data/sentiment/).
'''


import logging
import operator
import sys
from optparse import OptionParser
from time import time

import matplotlib.pyplot as plt
import numpy as np
from sklearn import metrics
from sklearn.datasets import fetch_20newsgroups
from sklearn.ensemble import AdaBoostClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.feature_selection import SelectFromModel
from sklearn.feature_selection import SelectKBest, chi2
from sklearn.linear_model import LogisticRegression
from sklearn.linear_model import PassiveAggressiveClassifier
from sklearn.linear_model import Perceptron
from sklearn.linear_model import RidgeClassifier
from sklearn.linear_model import SGDClassifier
from sklearn.naive_bayes import BernoulliNB, ComplementNB, MultinomialNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neighbors import NearestCentroid
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC
from sklearn.tree import DecisionTreeClassifier
from sklearn.utils.extmath import density
from datasets.load_dataset import load_imdb_reviews


if __name__ == '__main__':
    start = time()
    # Display progress logs on stdout
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s')

    op = OptionParser()
    op.add_option("--report",
                  action="store_true", dest="print_report",
                  help="Print a detailed classification report.")
    op.add_option("--chi2_select",
                  action="store", type="int", dest="select_chi2",
                  help="Select some number of features using a chi-squared test")
    op.add_option("--confusion_matrix",
                  action="store_true", dest="print_cm",
                  help="Print the confusion matrix.")
    op.add_option("--top10",
                  action="store_true", dest="print_top10",
                  help="Print ten most discriminative terms per class"
                       " for every classifier.")
    op.add_option("--all_categories",
                  action="store_true", dest="all_categories",
                  help="Whether to use all categories or not.")
    op.add_option("--use_hashing",
                  action="store_true",
                  help="Use a hashing vectorizer.")
    op.add_option("--n_features",
                  action="store", type=int, default=2 ** 16,
                  help="n_features when using the hashing vectorizer.")
    op.add_option("--filtered",
                  action="store_true",
                  help="Remove newsgroup information that is easily overfit: "
                       "headers, signatures, and quoting.")
    op.add_option("--just_miniproject_classifiers",
                  action="store_true", dest="just_miniproject_classifiers",
                  help="Use just the miniproject classifiers (1. LogisticRegression, 2. DecisionTreeClassifier, 3. LinearSVC (L1), 4. LinearSVC (L2), 5. AdaBoostClassifier, 6. RandomForestClassifier)")

    op.add_option("--plot_accurary_and_time",
                  action="store_true", dest="plot_accurary_and_time",
                  help="Plot training time and test time together with accuracy score")


    def is_interactive():
        return not hasattr(sys.modules['__main__'], '__file__')


    # work-around for Jupyter notebook and IPython console
    argv = [] if is_interactive() else sys.argv[1:]
    (opts, args) = op.parse_args(argv)
    if len(args) > 0:
        op.error("this script takes no arguments.")
        sys.exit(1)

    print(__doc__)
    op.print_help()
    print()

    '''
    #######################################
    # Load data from the training set
    #######################################
    Let’s load data from the newsgroups dataset which comprises around 18000 newsgroups posts on 20 topics split in two 
    subsets: one for training (or development) and the other one for testing (or for performance evaluation).
    '''


    if opts.all_categories:
        categories = None
    else:
        categories = [
            'alt.atheism',
            'talk.religion.misc',
            'comp.graphics',
            'sci.space',
        ]

    if opts.filtered:
        remove = ('headers', 'footers', 'quotes')
    else:
        remove = ()

    # TODO Use IMDB Reviews dataset
    # X, y = load_imdb_reviews('train', binary_labels=False, verbose=False)

    print("Loading 20 newsgroups dataset for categories:")
    print(categories if categories else "all")

    data_train = fetch_20newsgroups(subset='train', categories=categories,
                                    shuffle=True, random_state=42,
                                    remove=remove)

    data_test = fetch_20newsgroups(subset='test', categories=categories,
                                   shuffle=True, random_state=42,
                                   remove=remove)
    print('data loaded')

    # order of labels in `target_names` can be different from `categories`
    target_names = data_train.target_names


    def size_mb(docs):
        return sum(len(s.encode('utf-8')) for s in docs) / 1e6


    data_train_size_mb = size_mb(data_train.data)
    data_test_size_mb = size_mb(data_test.data)

    print("%d documents - %0.3fMB (training set)" % (
        len(data_train.data), data_train_size_mb))
    print("%d documents - %0.3fMB (test set)" % (
        len(data_test.data), data_test_size_mb))
    print("%d categories" % len(target_names))
    print()

    # split a training set and a test set
    y_train, y_test = data_train.target, data_test.target

    print("Extracting features from the training data using a sparse vectorizer")
    t0 = time()
    if opts.use_hashing:
        vectorizer = HashingVectorizer(stop_words='english', alternate_sign=False,
                                       n_features=opts.n_features)
        X_train = vectorizer.transform(data_train.data)
    else:
        vectorizer = TfidfVectorizer(sublinear_tf=True, max_df=0.5,
                                     stop_words='english')
        X_train = vectorizer.fit_transform(data_train.data)
    duration = time() - t0
    print("done in %fs at %0.3fMB/s" % (duration, data_train_size_mb / duration))
    print("n_samples: %d, n_features: %d" % X_train.shape)
    print()

    print("Extracting features from the test data using the same vectorizer")
    t0 = time()
    X_test = vectorizer.transform(data_test.data)
    duration = time() - t0
    print("done in %fs at %0.3fMB/s" % (duration, data_test_size_mb / duration))
    print("n_samples: %d, n_features: %d" % X_test.shape)
    print()

    # mapping from integer feature name to original token string
    if opts.use_hashing:
        feature_names = None
    else:
        feature_names = vectorizer.get_feature_names()

    if opts.select_chi2:
        print("Extracting %d best featureop.print_help()s by a chi-squared test" %
              opts.select_chi2)
        t0 = time()
        ch2 = SelectKBest(chi2, k=opts.select_chi2)
        X_train = ch2.fit_transform(X_train, y_train)
        X_test = ch2.transform(X_test)
        if feature_names:
            # keep selected feature names
            feature_names = [feature_names[i] for i
                             in ch2.get_support(indices=True)]
        print("done in %fs" % (time() - t0))
        print()

    if feature_names:
        feature_names = np.asarray(feature_names)


    def trim(s):
        """Trim string to fit on terminal (assuming 80-column display)"""
        return s if len(s) <= 80 else s[:77] + "..."

    '''
    ##############################################
    # Benchmark classifiers
    ##############################################
    
    We train and test the datasets with different classification models and get performance results for each model.
    '''

    def benchmark(clf, classifier_name):
        print('_' * 80)
        print("Training: ")
        print(clf)
        t0 = time()
        clf.fit(X_train, y_train)
        train_time = time() - t0
        print("train time: %0.3fs" % train_time)

        t0 = time()
        pred = clf.predict(X_test)
        test_time = time() - t0
        print("test time:  %0.3fs" % test_time)

        score = metrics.accuracy_score(y_test, pred)
        print("accuracy:   %0.3f" % score)

        if hasattr(clf, 'coef_'):
            print("dimensionality: %d" % clf.coef_.shape[1])
            print("density: %f" % density(clf.coef_))

            if opts.print_top10 and feature_names is not None:
                print("top 10 keywords per class:")
                for i, label in enumerate(target_names):
                    top10 = np.argsort(clf.coef_[i])[-10:]
                    print(trim("%s: %s" % (label, " ".join(feature_names[top10]))))
            print()

        if opts.print_report:
            print("classification report:")
            print(metrics.classification_report(y_test, pred,
                                                target_names=target_names))

        if opts.print_cm:
            print("confusion matrix:")
            print(metrics.confusion_matrix(y_test, pred))

        print()
        # clf_descr = str(clf).split('(')[0]
        return classifier_name, score, train_time, test_time


    results = []
    if opts.just_miniproject_classifiers:
        for clf, classifier_name in (
                (LogisticRegression(), "Logistic Regression"),
                (DecisionTreeClassifier(), "Decision Tree Classifier"),
                (LinearSVC(penalty="l2", dual=False, tol=1e-3), "Linear SVC (penalty = L2)"),
                (AdaBoostClassifier(), "Ada Boost Classifier"),
                (RandomForestClassifier(), "Random forest")):
            print('=' * 80)
            print(classifier_name)
            results.append(benchmark(clf, classifier_name))
    else:
        for clf, classifier_name in (
                (RidgeClassifier(tol=1e-2, solver="sag"), "Ridge Classifier"),
                (Perceptron(max_iter=50), "Perceptron"),
                (PassiveAggressiveClassifier(max_iter=50), "Passive-Aggressive"),
                (KNeighborsClassifier(n_neighbors=10), "kNN"),
                (LogisticRegression(), "Logistic Regression"),
                (DecisionTreeClassifier(), "Decision Tree Classifier"),
                (LinearSVC(penalty="l2", dual=False, tol=1e-3), "Linear SVC (penalty = L2)"),
                (LinearSVC(penalty="l1", dual=False, tol=1e-3), "Linear SVC (penalty = L1)"),
                (SGDClassifier(alpha=.0001, max_iter=50, penalty="l2"), "SGD Classifier (penalty = L2)"),
                (SGDClassifier(alpha=.0001, max_iter=50, penalty="l2"), "SGD Classifier (penalty = L1)"),
                (AdaBoostClassifier(), "Ada Boost Classifier"),
                (RandomForestClassifier(), "Random forest")):
            print('=' * 80)
            print(classifier_name)
            results.append(benchmark(clf, classifier_name))

        # Train SGD with Elastic Net penalty
        print('=' * 80)
        print("SGDClassifier Elastic-Net penalty")
        results.append(benchmark(SGDClassifier(alpha=.0001, max_iter=50, penalty="elasticnet"), "SGDClassifier using Elastic-Net penalty"))

        # Train NearestCentroid without threshold
        print('=' * 80)
        print("NearestCentroid (aka Rocchio classifier)")
        results.append(benchmark(NearestCentroid(), "NearestCentroid (aka Rocchio classifier)"))

        # Train sparse Naive Bayes classifiers
        print('=' * 80)
        print("Naive Bayes")
        results.append(benchmark(MultinomialNB(alpha=.01), "MultinomialNB(alpha=.01)"))
        results.append(benchmark(BernoulliNB(alpha=.01), "BernoulliNB(alpha=.01)"))
        results.append(benchmark(ComplementNB(alpha=.1), "ComplementNB(alpha=.1)"))

        print('=' * 80)
        print("LinearSVC with L1-based feature selection")
        # The smaller C, the stronger the regularization.
        # The more regularization, the more sparsity.
        results.append(benchmark(Pipeline([
          ('feature_selection', SelectFromModel(LinearSVC(penalty="l1", dual=False, tol=1e-3))),
          ('classification', LinearSVC(penalty="l2"))]), "LinearSVC with L1-based feature selection"))


    '''
    ##############
    # Add plots
    ##############
    
    The bar plot indicates the accuracy, training time (normalized) and test time (normalized) of each classifier.
    
    '''

    indices = np.arange(len(results))

    results = [[x[i] for x in results] for i in range(4)]

    clf_names, score, training_time, test_time = results
    training_time = np.array(training_time) / np.max(training_time)
    test_time = np.array(test_time) / np.max(test_time)

    plt.figure(figsize=(12, 8))
    if opts.filtered:
        plt.title("Accuracy score for the 20 news group dataset (removing headers signatures and quoting)")
    else:
        plt.title("Accuracy score for the 20 news group dataset")
    plt.barh(indices, score, .2, label="score", color='navy')
    if opts.plot_accurary_and_time:
        plt.barh(indices + .3, training_time, .2, label="training time", color='c')
        plt.barh(indices + .6, test_time, .2, label="test time", color='darkorange')
    plt.yticks(())
    plt.legend(loc='best')
    plt.subplots_adjust(left=.25)
    plt.subplots_adjust(top=.95)
    plt.subplots_adjust(bottom=.05)

    for i, c, s, tr, te in zip(indices, clf_names, score, training_time, test_time):
        plt.text(-.3, i, c)
        plt.text(tr / 2, i + .3, round(tr, 2), ha='center', va='center', color='white')
        plt.text(te / 2, i + .6, round(te, 2), ha='center', va='center', color='white')
        plt.text(s / 2, i, round(s, 2), ha='center', va='center', color='white')

    plt.tight_layout()

    plt.show()

    print("Final classification report: ")
    classifier_name_list = results[0]
    accuracy_score_list = results[1]
    train_time_list = results[2]
    test_time_list = results[3]
    index = 1
    for classifier_name, accuracy_score, train_time, test_time in zip(classifier_name_list, accuracy_score_list, train_time_list, test_time_list):
        if classifier_name in ["Logistic Regression", "Decision Tree Classifier", "Linear SVC (penalty = L2)", "Linear SVC (penalty = L1)", "Ada Boost Classifier", "Random forest"]:
            classifier_name = classifier_name + " [MANDATORY FOR COMP 551, ASSIGNMENT 2]"
        print("{}) {}\n\t\tAccuracy score = {}\t\tTraining time = {}\t\tTest time = {}\n".format(index, classifier_name, accuracy_score, train_time, test_time))
        index = index + 1

    print("\n\nBest algorithm:")
    index_max_accuracy_score, accuracy_score = max(enumerate(accuracy_score_list), key=operator.itemgetter(1))

    print("===> {}) {}\n\t\tAccuracy score = {}\t\tTraining time = {}\t\tTest time = {}\n".format(
        index_max_accuracy_score + 1,
        classifier_name_list[index_max_accuracy_score],
        accuracy_score_list[index_max_accuracy_score],
        train_time_list[index_max_accuracy_score],
        test_time_list[index_max_accuracy_score]))

    print('\n\nDONE!')

    print("Program finished. It took {} seconds".format(time() - start))
