<?php
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, GET, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');
header('Content-Type: application/json');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { exit(0); }

$file = 'accounts.json';
$inputData = json_decode(file_get_contents('php://input'), true);

if ($inputData && isset($inputData['email'])) {
    $currentAccounts = [];
    if (file_exists($file)) {
        $jsonContent = file_get_contents($file);
        $currentAccounts = json_decode($jsonContent, true) ?: [];
    }
    
    $email = strtolower(trim($inputData['email']));
    $currentAccounts[$email] = $inputData;
    
    if (file_put_contents($file, json_encode($currentAccounts, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE))) {
        echo json_encode(['success' => true, 'message' => 'تم الحفظ في ملف accounts.json بنجاح']);
    } else {
        echo json_encode(['success' => false, 'message' => 'تعذر الكتابة في الملف']);
    }
} else {
    echo json_encode(['success' => false, 'message' => 'بيانات غير مكتملة']);
}
?>
