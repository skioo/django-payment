from django.http import HttpResponse
import datetime
from paybox_test.paybox_system import PayboxSystemTransaction
from paybox_test.paybox_direct import PayboxDirectTransaction
from paybox_test.paybox_direct_plus import PayboxDirectPlusTransaction


def paybox_system(request):
    transaction = PayboxSystemTransaction(
        total="10000",
        cmd="RANDOM",
        porteur="arlusishmael@gmail.com",
        time=datetime.datetime.now().isoformat()
    )
    transaction.post_to_paybox()
    form = transaction.construct_html_form()
    return HttpResponse(form)


def paybox_system_subscription(request):
    transaction = PayboxSystemTransaction(
        total="200000",
        cmd="RANDOM2",
        porteur="wedavamagomere@gmail.com",
        time=datetime.datetime.now().isoformat(),
        subscription=True,
        subscription_amount="200000",
        nbpaie="0",
        freq="1",
        quand="0",
        delais="2"
    )
    transaction.post_to_paybox()
    form = transaction.construct_html_form()
    return HttpResponse(form)


def paybox_direct(request):
    transaction = PayboxDirectTransaction(
        operation_type="00001",
        montant="40000",
        reference="RANDOMynu",
        cle="1999888I",
        cvv="123",
        porteur="1111222233334444",
        dateval="1219",
        secure_3d=False,
        activite="024",
        dateq=datetime.datetime.strftime(datetime.datetime.now(), '%d%m%Y'),
        pays=""
    )
    #authorize = transaction.post_to_paybox(numquestion="0000000005", operation_type="00001")
    #sleep(1)
    debit = transaction.post_to_paybox(numquestion="0000000006", operation_type="00002")
    #sleep(1)
    #refund = transaction.post_to_paybox(numquestion="0000000007", operation_type="00014")
    return HttpResponse("")


def paybox_direct_3d(request):
    transaction = PayboxDirectTransaction(
        operation_type="00001",
        montant="1000",
        reference="yrjhvjgjixdrdxbutr",
        cle="1999888I",
        cvv="123",
        porteur="4012001037141112",
        dateval="1216",
        secure_3d=True,
        url_http_direct="https://dd883f2b.ngrok.io/callback1",
        activite="024",
        dateq=datetime.datetime.strftime(datetime.datetime.now(), '%d%m%Y'),
        pays="",
        devise="952"
    )
    authorize_3d = transaction.remote_mpi_authenticate(session_id="buuhjfgdffcwtheg")
    return authorize_3d


def paybox_direct_plus(request):
    transaction = PayboxDirectPlusTransaction(
        operation_type="00001",
        montant="1000",
        reference="yrjhvbngjixdrdtr",
        cle="1999888I",
        cvv="123",
        porteur="1111222233334444",
        dateval="1219",
        url_http_direct="https://dd883f2b.ngrok.io/callback",
        activite="027",
        dateq=datetime.datetime.strftime(datetime.datetime.now(), '%d%m%Y'),
        pays="",
        devise="978",
        refabonne="ITWORKhtbSMAN"
    )
    #register = transaction.post_to_paybox(numquestion="0000000015", operation_type="00056")
    #sleep(1)
    #debit = transaction.post_to_paybox(numquestion="0000000016", operation_type="00052")
    #sleep(1)
    authorize_and_capture = transaction.post_to_paybox(numquestion="0000000017", operation_type="00053")
    return HttpResponse()

