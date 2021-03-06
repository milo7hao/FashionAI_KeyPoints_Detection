# -- coding: utf-8 --
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import torch
import torch.nn as nn
import math
import torch.nn.functional as F

############################################################
#  ResNet
############################################################
def conv3x3(in_planes, out_planes, stride=1):
    "3x3 convolution with padding"
    return nn.Conv2d(in_planes, out_planes, kernel_size=3, stride=stride,
                     padding=1, bias=False)
#浅层网络用的2个卷积的模块
class BasicBlock(nn.Module):
    expansion = 1

    def __init__(self, inplanes, planes, stride=1, downsample=None):
        super(BasicBlock, self).__init__()
        self.conv1 = conv3x3(inplanes, planes, stride)
        self.bn1 = nn.BatchNorm2d(planes)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = conv3x3(planes, planes)
        self.bn2 = nn.BatchNorm2d(planes)
        self.downsample = downsample
        self.stride = stride

    def forward(self, x):
        residual = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)

        if self.downsample is not None:
            residual = self.downsample(x)

        out += residual
        out = self.relu(out)

        return out

#这是深层网络用的3个卷积模块
class Bottleneck(nn.Module):
    expansion = 4

    def __init__(self, inplanes, planes, stride=1, downsample=None):
        super(Bottleneck, self).__init__()
        self.conv1 = nn.Conv2d(inplanes, planes, kernel_size=1, bias=False)
        self.bn1 = nn.BatchNorm2d(planes)
        self.conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=stride,
                               padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(planes)
        self.conv3 = nn.Conv2d(planes, planes * 4, kernel_size=1, bias=False)
        self.bn3 = nn.BatchNorm2d(planes * 4)
        self.relu = nn.ReLU(inplace=True)
        self.downsample = downsample
        self.stride = stride

    def forward(self, x):
        residual = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)
        out = self.relu(out)

        out = self.conv3(out)
        out = self.bn3(out)

        if self.downsample is not None:
            residual = self.downsample(x)

        out += residual
        out = self.relu(out)

        return out


class ResNet(nn.Module):
#这里的layer是代表[3,4,6,3]
    def __init__(self, block, layers, num_classes=1000):
        self.inplanes = 64
        super(ResNet, self).__init__()
        #输入图像是3通道的，输出是64通道，卷积核是7*7，步长2，padding3
        self.conv1 = nn.Conv2d(3, 64, kernel_size=7, stride=2, padding=3,
                               bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        self.relu = nn.ReLU(inplace=True)
        #到这里输出的feature通道数还是64，layer的列表代表的是卷积核的大小
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        self.layer1 = self._make_layer(block, 64, layers[0])
        self.layer2 = self._make_layer(block, 128, layers[1], stride=2)
        self.layer3 = self._make_layer(block, 256, layers[2], stride=2)
        self.layer4 = self._make_layer(block, 512, layers[3], stride=2)
        #参数初始化
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                m.weight.data.normal_(0, math.sqrt(2. / n))
            elif isinstance(m, nn.BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()

    def _make_layer(self, block, planes, blocks, stride=1):
        downsample = None
        if stride != 1 or self.inplanes != planes * block.expansion:
            downsample = nn.Sequential(
                nn.Conv2d(self.inplanes, planes * block.expansion,
                          kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(planes * block.expansion),
            )

        layers = []
        layers.append(block(self.inplanes, planes, stride, downsample))
        self.inplanes = planes * block.expansion
        for i in range(1, blocks):
            layers.append(block(self.inplanes, planes))

        return nn.Sequential(*layers)#吧这些层加起来

    def load_weights(self, path):
        model_dict = self.state_dict()
        print('loading model from {}'.format(path))
        try:
            #state_dict = torch.load(self.path)
            # self.load_state_dict({k: v for k, v in state_dict.items() if k in self.state_dict()})
            pretrained_dict = torch.load(path)
            from collections import OrderedDict
            tmp = OrderedDict()
            for k,v in pretrained_dict.items():
                if k in model_dict:
                    tmp[k] = v
            # pretrained_dict = {k: v for k, v in pretrained_dict.items() if k in model_dict}
            # model_dict.update(pretrained_dict)
            model_dict.update(tmp)
            self.load_state_dict(model_dict)
        except:
            print ('loading model failed, {} may not exist'.format(path))

    def forward(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        C1 = self.maxpool(x)

        C2 = self.layer1(C1)
        C3 = self.layer2(C2)
        C4 = self.layer3(C3)
        C5 = self.layer4(C4)

        return C1, C2, C3, C4, C5

############################################################
#  FPN Graph
############################################################

class FPN(nn.Module): # xavier_fill as default
    def __init__(self, out_channels):
        super(FPN, self).__init__()
        self.out_channels = out_channels
        self.P6 = nn.MaxPool2d(kernel_size=1, stride=2, padding=0, ceil_mode=False)
        self.P5_conv1 = nn.Conv2d(2048, self.out_channels, kernel_size=1, stride=1)
 
        self.P4_conv1 =  nn.Conv2d(1024, self.out_channels, kernel_size=1, stride=1)
        self.P4_conv2 = nn.Conv2d(self.out_channels, self.out_channels, kernel_size=3, stride=1, padding=1)

        self.P3_conv1 = nn.Conv2d(512, self.out_channels, kernel_size=1, stride=1)
        self.P3_conv2 = nn.Conv2d(self.out_channels, self.out_channels, kernel_size=3, stride=1, padding=1)
        self.P2_conv1 = nn.Conv2d(256, self.out_channels, kernel_size=1, stride=1)
        self.P2_conv2 = nn.Conv2d(self.out_channels, self.out_channels, kernel_size=3, stride=1, padding=1)

    def forward(self, C1, C2, C3 ,C4, C5):

        p5_out = self.P5_conv1(C5)
        
        p4_out = torch.add(self.P4_conv1(C4), F.upsample_nearest(p5_out, scale_factor=2))
        p3_out = torch.add(self.P3_conv1(C3), F.upsample_nearest(p4_out, scale_factor=2))
        p2_out = torch.add(self.P2_conv1(C2), F.upsample_nearest(p3_out, scale_factor=2))

        p4_out = self.P4_conv2(p4_out)
        p3_out = self.P3_conv2(p3_out)
        p2_out = self.P2_conv2(p2_out)

        # P6 is used for the 5th anchor scale in RPN. Generated by
        # subsampling from P5 with stride of 2.
        p6_out = self.P6(p5_out)

        return p2_out, p3_out, p4_out, p5_out, p6_out


############################################################
#  Pose Estimation Graph
############################################################

class pose_estimation(nn.Module):
    def __init__(self, class_num, pretrain=True):
        super(pose_estimation, self).__init__()
        self.resnet = ResNet(Bottleneck, [3, 4, 6, 3]) # resnet101
        if pretrain == True:
            self.model_path = '../utils/resnet50-19c8e357.pth'
            self.resnet.load_weights(self.model_path)
        self.apply_fix()#固定resnet的参数
        self.out_channels = 256
        self.fpn = FPN(self.out_channels)

        # self.block = nn.Sequential(nn.Conv2d(256, 128, 1, 1, 0), nn.ReLU(inplace=True),
        #                               nn.Conv2d(128, 128, 3, 1, 1), nn.ReLU(inplace=True),
        #                               nn.Conv2d(128, 128, 3, 1, 1), nn.ReLU(inplace=True),
        #                               nn.Conv2d(128, 128, 3, 1, 1), nn.ReLU(inplace=True),
        #                               nn.Conv2d(128, 256, 3, 1, 1), nn.ReLU(inplace=True)
        #                               )
        # self._init_weights(self.block)13,15,14,4,7
        #分不同的情况搭建网络模型
        if(class_num == 13 ):
            self.predict = nn.Sequential(nn.Conv2d(768, 128, 3, 1, 1), nn.ReLU(inplace=True),
                                         nn.Conv2d(128, 128, 3, 1, 1), nn.ReLU(inplace=True),
                                         nn.Conv2d(128, 128, 3, 1, 1), nn.ReLU(inplace=True),
                                         nn.Conv2d(128, 128, 3, 1, 1), nn.ReLU(inplace=True),
                                         nn.Conv2d(128, 14, 3, 1, 1))
        elif(class_num==15):
            self.predict = nn.Sequential(nn.Conv2d(768, 128, 3, 1, 1), nn.ReLU(inplace=True),
                                         nn.Conv2d(128, 128, 3, 1, 1), nn.ReLU(inplace=True),
                                         nn.Conv2d(128, 128, 3, 1, 1), nn.ReLU(inplace=True),
                                         nn.Conv2d(128, 128, 3, 1, 1), nn.ReLU(inplace=True),
                                         nn.Conv2d(128, 16, 3, 1, 1))
        elif (class_num == 14):
            self.predict = nn.Sequential(nn.Conv2d(768, 128, 3, 1, 1), nn.ReLU(inplace=True),
                                         nn.Conv2d(128, 128, 3, 1, 1), nn.ReLU(inplace=True),
                                         nn.Conv2d(128, 128, 3, 1, 1), nn.ReLU(inplace=True),
                                         nn.Conv2d(128, 128, 3, 1, 1), nn.ReLU(inplace=True),
                                         nn.Conv2d(128, 15, 3, 1, 1))
        elif (class_num == 4):
            self.predict = nn.Sequential(nn.Conv2d(768, 128, 3, 1, 1), nn.ReLU(inplace=True),
                                         nn.Conv2d(128, 128, 3, 1, 1), nn.ReLU(inplace=True),
                                         nn.Conv2d(128, 128, 3, 1, 1), nn.ReLU(inplace=True),
                                         nn.Conv2d(128, 128, 3, 1, 1), nn.ReLU(inplace=True),
                                         nn.Conv2d(128, 5, 3, 1, 1))
        elif (class_num == 7):
            self.predict = nn.Sequential(nn.Conv2d(768, 128, 3, 1, 1), nn.ReLU(inplace=True),
                                         nn.Conv2d(128, 128, 3, 1, 1), nn.ReLU(inplace=True),
                                         nn.Conv2d(128, 128, 3, 1, 1), nn.ReLU(inplace=True),
                                         nn.Conv2d(128, 128, 3, 1, 1), nn.ReLU(inplace=True),
                                         nn.Conv2d(128, 8, 3, 1, 1))



        self._init_weights(self.predict)
                                        
	    
	    
    def _gaussian_init_conv(self, conv):
        if isinstance(conv, nn.Conv2d):
            conv.weight.data.normal_(0, 0.01)
            if conv.bias is not None:
                conv.bias.data.zero_()
			    
    def _init_weights(self, model):
        for m in model:
            if isinstance(m, nn.Conv2d):
                m.weight.data.normal_(0, 0.01)
                if m.bias is not None:
                    m.bias.data.zero_()
			        
	#固定头两层的参数
    def apply_fix(self):
        # 1. fix bn
        # 2. fix conv1 conv2
        for param in self.resnet.conv1.parameters():
            param.requires_grad = False
        for param in self.resnet.layer1.parameters():
            param.requires_grad = False

    def forward(self, x):
        C1, C2, C3, C4, C5 = self.resnet(x)
        P2, P3, P4, P5, P6 = self.fpn(C1, C2, C3, C4, C5)
		
        P4_x2 = F.upsample(P4, scale_factor=2)
        P5_x4 = F.upsample(P5, scale_factor=4)
        featuer_cat = torch.cat([P3, P4_x2, P5_x4],1)
        out = self.predict(featuer_cat)
        return out
		